import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { ApiError, configureAuth, serverReachable, startAuthGeneration } from "@/api/client";
import { api } from "@/api/endpoints";
import type { TokenResponse, User } from "@/api/types";
import { diag } from "@/lib/diagnostics";

import { AuthContext, type AuthContextValue } from "./context";
import { forgetDeviceUser, readDeviceUser, rememberDeviceUser, type DeviceUser } from "./deviceUser";
import { clearLocalWork } from "./localWork";
import { beginAttempt, dropAttempt, forgetAttempts, RACE_RETRY_MS, settleAttempt, withRefreshLock } from "./refreshAttempt";
import { forgetLegacySession, isExpired, refreshDelay, sessionFromToken, type Session } from "./session";

/** One refresh request, with an attempt key that is kept until its outcome is known. */
async function sendRefresh(): Promise<TokenResponse> {
  const key = beginAttempt();
  try {
    const response = await api.refresh(key);
    settleAttempt(key);
    return response;
  } catch (error) {
    if (error instanceof ApiError) {
      // Someone else's attempt used the cookie: this key rotated nothing.
      if (error.code === "refresh_race") dropAttempt(key);
      // Refused for good (signed out, expired, revoked): nothing left to recover.
      else if (error.status === 401 || error.status === 403) settleAttempt(key);
      // A network error or a server error: the outcome is unknown, so the key is kept.
    }
    throw error;
  }
}

/**
 * A session started or ended: everything cached came from the previous one. Not only the "me"
 * queries hold personal data (a question's past answers, track progress, a submission are cached
 * under other keys), so all of it goes, and queries still retrying for that session stop.
 */
function forgetSessionData(queryClient: QueryClient): void {
  void queryClient.cancelQueries();
  queryClient.removeQueries();
}

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
  const lastFailure = useRef<"network" | "rejected" | "superseded" | null>(null);
  // Changes whenever the session is replaced or ended (sign-in, sign-out). A refresh that started
  // before then must not bring its result back: a late response can't sign anyone back in.
  const epoch = useRef(0);
  // One refresh at a time in this tab: concurrent 401s and the timer share the same request.
  const inFlight = useRef<Promise<string | null> | null>(null);
  // A ref lets the API client read the current token synchronously without re-wiring.
  const sessionRef = useRef(session);
  useLayoutEffect(() => {
    sessionRef.current = session;
  }, [session]);

  const clear = useCallback((reason: string | null) => {
    epoch.current += 1;
    startAuthGeneration(); // a late 401 for this session's requests can't refresh or sign anyone in
    inFlight.current = null;
    forgetAttempts();
    sessionRef.current = null;
    setSession(null);
    setOfflineUser(null);
    setSignedOutReason(reason);
    setSignedOutDeliberately(reason === null);
    forgetSessionData(queryClient);
  }, [queryClient]);

  /** A new sign-in (login, register, guest, password change): start a fresh session. */
  const adopt = useCallback((response: TokenResponse): User => {
    const next = sessionFromToken(response);
    epoch.current += 1;
    startAuthGeneration(); // requests of the previous session are never retried as this one
    inFlight.current = null;
    forgetAttempts();
    sessionRef.current = next;
    setSession(next);
    setSignedOutReason(null);
    setSignedOutDeliberately(false);
    setOfflineUser(null);
    rememberDeviceUser(next.user);
    forgetSessionData(queryClient);
    return next.user;
  }, [queryClient]);

  const refreshNow = useCallback((): Promise<string | null> => {
    if (inFlight.current) return inFlight.current;
    const startedIn = epoch.current;
    const attempt = async (): Promise<string | null> => {
      // Known to be offline: don't send a refresh that can't succeed. (A refresh the server
      // receives but whose answer is lost uses up the rotating cookie; see refreshAttempt.ts.)
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        lastFailure.current = "network";
        return null;
      }
      for (let tries = 0; ; tries++) {
        try {
          const response = await withRefreshLock(sendRefresh);
          if (epoch.current !== startedIn) {
            // Signed out (or in as someone else) while this was on its way: drop it.
            diag("auth", { event: "refresh", outcome: "discarded" });
            lastFailure.current = "superseded";
            return null;
          }
          const next = sessionFromToken(response);
          sessionRef.current = next; // the API client reads this synchronously for its retry
          setSession(next); // same user, so cached data stays valid
          setOfflineUser(null);
          rememberDeviceUser(next.user);
          lastFailure.current = null;
          diag("auth", { event: "refresh", outcome: "ok", tries });
          return next.token;
        } catch (error) {
          const code = error instanceof ApiError ? error.code : "unknown";
          if (epoch.current !== startedIn) {
            lastFailure.current = "superseded";
            return null;
          }
          // Another tab, or this page before a reload, is using the cookie right now: wait for
          // it to finish (the browser then has the new cookie) and try again, a few times.
          const wait = RACE_RETRY_MS[tries];
          if (code === "refresh_race" && wait !== undefined) {
            diag("auth", { event: "refresh", outcome: "race_retry", tries });
            await new Promise((resolve) => window.setTimeout(resolve, wait));
            continue;
          }
          diag("auth", { event: "refresh", outcome: code, tries });
          lastFailure.current = code === "network_error" ? "network" : "rejected";
          return null;
        }
      }
    };
    const promise = attempt().finally(() => {
      if (inFlight.current === promise) inFlight.current = null;
    });
    inFlight.current = promise;
    return promise;
  }, []);

  // Wire authentication before child query subscriptions issue their initial requests.
  useLayoutEffect(() => {
    configureAuth(
      () => {
        const current = sessionRef.current;
        return current && !isExpired(current) ? current.token : null;
      },
      // Only a session that was still on ends here: after a deliberate sign-out, a late 401
      // from a request that was already on its way must not turn into "your session ended".
      () => { if (sessionRef.current) clear("Your session ended. Please sign in again."); },
      async () => {
        const token = await refreshNow();
        // Couldn't reach the server (or the answer was lost): not signed out. The request fails
        // with a network error, and the next refresh recovers the session with the same key.
        if (!token && lastFailure.current === "network") {
          throw new ApiError(0, "network_error", "Can't reach the CodeCoach server. Check your connection and try again.");
        }
        return token;
      },
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
        if (!token && lastFailure.current === "rejected") clear("Your session ended. Please sign in again.");
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
