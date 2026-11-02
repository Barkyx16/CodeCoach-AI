import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { ApiError, configureAuth } from "@/api/client";
import { api } from "@/api/endpoints";
import type { TokenResponse, User } from "@/api/types";

import { AuthContext, type AuthContextValue } from "./context";
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
  // A ref lets the API client read the current token synchronously without re-wiring.
  const sessionRef = useRef(session);
  useLayoutEffect(() => {
    sessionRef.current = session;
  }, [session]);

  const clear = useCallback((reason: string | null) => {
    sessionRef.current = null;
    setSession(null);
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
    queryClient.removeQueries({ queryKey: ["me"] });
    return next.user;
  }, [queryClient]);

  // One refresh at a time: concurrent 401s and the timer share the same request.
  const inFlight = useRef<Promise<string | null> | null>(null);
  const refreshNow = useCallback((): Promise<string | null> => {
    if (inFlight.current) return inFlight.current;
    const attempt = async (): Promise<string | null> => {
      try {
        const response = await api.refresh();
        const next = sessionFromToken(response);
        sessionRef.current = next; // the API client reads this synchronously for its retry
        setSession(next); // same user, so cached data stays valid
        return next.token;
      } catch (error) {
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
    void refreshNow().finally(() => setIsRestoring(false));
  }, [refreshNow]);

  // Refresh a minute before the access token expires, so requests never wait on it.
  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(() => {
      void refreshNow().then((token) => {
        if (!token) clear("Your session ended. Please sign in again.");
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
    continueAsGuest: async (displayName) => adopt(await api.guest(displayName)),
    logout: async () => {
      try {
        await api.logout(); // revokes the token server-side too
      } catch {
        /* still sign out locally even if the network call fails */
      }
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
    forget: () => clear(null),
  }), [session, isRestoring, signedOutReason, signedOutDeliberately, adopt, clear]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
