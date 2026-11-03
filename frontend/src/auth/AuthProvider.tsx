import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { ApiError, configureAuth, serverReachable } from "@/api/client";
import { api } from "@/api/endpoints";
import type { TokenResponse, User } from "@/api/types";

import { AuthContext, type AuthContextValue } from "./context";
import { forgetDeviceUser, readDeviceUser, rememberDeviceUser, type DeviceUser } from "./deviceUser";
import { clearLocalWork } from "./localWork";
import { forgetLegacySession, isExpired, refreshDelay, sessionFromToken, type Session } from "./session";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(null);
  // True until the first refresh attempt answers whether the HttpOnly cookie holds a session.
  const [isRestoring, setIsRestoring] = useState(true);
  const [signedOutReason, setSignedOutReason] = useState<string | null>(null);
  // True after the user chose to leave (logout, account deletion), so route guards send them
  // home instead of to the login page.
  const [signedOutDeliberately, setSignedOutDeliberately] = useState(false);
  // The server couldn't be reached to check the session (offline). Not "signed out": the last
  // account on this device, so its drafts stay visible; checked again when the network returns.
  const [offlineUser, setOfflineUser] = useState<DeviceUser | null>(null);
  const lastFailure = useRef<"network" | "rejected" | null>(null);
  // A ref lets the API client read the current token synchronously without re-wiring.
  const sessionRef = useRef(session);
  useLayoutEffect(() => {
    sessionRef.current = session;
  }, [session]);

  const clear = useCallback((reason: string | null) => {
    sessionRef.current = null;
    setSession(null);
    setOfflineUser(null);
    setSignedOutReason(reason);
    setSignedOutDeliberately(reason === null);
    queryClient.removeQueries({ queryKey: ["me"] });
  }, [queryClient]);

  /** A new sign-in (login, register, guest, password change): start a fresh session. */
  const adopt = useCallback((response: TokenResponse): User => {
    const next = sessionFromToken(response);
    sessionRef.current = next;
    setSession(next);
    setSignedOutReason(null);
    setSignedOutDeliberately(false);
    setOfflineUser(null);
    rememberDeviceUser(next.user);
    queryClient.removeQueries({ queryKey: ["me"] });
    return next.user;
  }, [queryClient]);

  // One refresh at a time: concurrent 401s and the timer share the same request.
  const inFlight = useRef<Promise<string | null> | null>(null);
  const refreshNow = useCallback((): Promise<string | null> => {
    if (inFlight.current) return inFlight.current;
    const attempt = async (): Promise<string | null> => {
      // Known to be offline: don't send a refresh that can't succeed. (A refresh the server
      // receives but whose answer is lost would use up the rotating cookie.)
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        lastFailure.current = "network";
        return null;
      }
      try {
        const response = await api.refresh();
        const next = sessionFromToken(response);
        sessionRef.current = next; // the API client reads this synchronously for its retry
        setSession(next); // same user, so cached data stays valid
        setOfflineUser(null);
        rememberDeviceUser(next.user);
        lastFailure.current = null;
        return next.token;
      } catch (error) {
        lastFailure.current = error instanceof ApiError && error.code === "network_error" ? "network" : "rejected";
        // Another tab rotated the cookie a moment ago; the browser now has the new one.
        if (error instanceof ApiError && error.code === "refresh_race") {
          await new Promise((resolve) => window.setTimeout(resolve, 400));
          try {
            const response = await api.refresh();
            const next = sessionFromToken(response);
            sessionRef.current = next;
            setSession(next);
            return next.token;
          } catch {
            return null;
          }
        }
        return null;
      }
    };
    inFlight.current = attempt().finally(() => { inFlight.current = null; });
    return inFlight.current;
  }, []);

  // Wire authentication before child query subscriptions issue their initial requests.
  useLayoutEffect(() => {
    configureAuth(
      () => {
        const current = sessionRef.current;
        return current && !isExpired(current) ? current.token : null;
      },
      () => clear("Your session ended. Please sign in again."),
      refreshNow,
    );
    return () => configureAuth(() => null, () => {});
  }, [clear, refreshNow]);

  // On load: restore the session from the HttpOnly cookie (nothing is kept in localStorage).
  // Goes through the shared single-flight refresh: React may run this effect twice in
  // development, and two tabs may load at once. Two refreshes with one cookie would rotate it
  // and then report a race, which must not read as "signed out".
  useEffect(() => {
    forgetLegacySession();
    void refreshNow().then((token) => {
      if (!token && lastFailure.current === "network") setOfflineUser(readDeviceUser());
    }).finally(() => setIsRestoring(false));
  }, [refreshNow]);

  // Back online after a check that couldn't reach the server: check again.
  useEffect(() => {
    const retry = async () => {
      if (sessionRef.current && !isExpired(sessionRef.current)) return;
      if (!offlineUser && !sessionRef.current) return;
      if (!(await serverReachable())) return; // still not really online: try on the next "online"
      const token = await refreshNow();
      if (!token && lastFailure.current === "rejected") clear("Your session ended. Please sign in again.");
    };
    const onOnline = () => void retry();
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [offlineUser, refreshNow, clear]);

  // Refresh a minute before the access token expires, so requests never wait on it.
  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(() => {
      void refreshNow().then((token) => {
        // Offline isn't signed out: keep the session and try again when the network returns.
        if (!token && lastFailure.current !== "network") clear("Your session ended. Please sign in again.");
      });
    }, refreshDelay(session));
    return () => window.clearTimeout(timer);
  }, [session, refreshNow, clear]);

  const value = useMemo<AuthContextValue>(() => ({
    user: session?.user ?? null,
    isAuthenticated: session !== null,
    isRestoring,
    signedOutReason,
    signedOutDeliberately,
    login: async (body) => adopt(await api.login(body)),
    register: async (body) => adopt(await api.register(body)),
    continueAsGuest: async (displayName, careerTrack) => adopt(await api.guest(displayName, careerTrack)),
    logout: async () => {
      try {
        await api.logout(); // ends this device's refresh cookie server-side
      } catch {
        /* still sign out locally even if the network call fails */
      }
      const id = session?.user.id ?? offlineUser?.id;
      if (id) clearLocalWork(id); // drafts and pending sync for this account, on this device
      forgetDeviceUser();
      clear(null);
    },
    logoutAll: async () => {
      await api.logoutAll(); // if this fails, say so rather than pretend other devices are out
      if (session) clearLocalWork(session.user.id);
      forgetDeviceUser();
      clear(null);
    },
    setUser: (user) => {
      setSession((current) => {
        if (!current) return current;
        const next = { ...current, user };
        sessionRef.current = next;
        return next;
      });
    },
    adoptToken: (response) => {
      adopt(response);
    },
    forget: () => {
      const id = session?.user.id;
      if (id) clearLocalWork(id);
      forgetDeviceUser();
      clear(null);
    },
    offlineUser,
    draftScope: session?.user.id ?? offlineUser?.id ?? "anon",
  }), [session, isRestoring, signedOutReason, signedOutDeliberately, adopt, clear, offlineUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
