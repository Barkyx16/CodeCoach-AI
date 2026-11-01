import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { configureAuth } from "@/api/client";
import { api } from "@/api/endpoints";
import type { TokenResponse, User } from "@/api/types";

import { AuthContext, type AuthContextValue } from "./context";
import { isExpired, loadSession, saveSession, sessionFromToken, type Session } from "./session";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(() => loadSession());
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
    saveSession(null);
    setSession(null);
    setSignedOutReason(reason);
    setSignedOutDeliberately(reason === null);
    queryClient.removeQueries({ queryKey: ["me"] });
  }, [queryClient]);

  useEffect(() => {
    configureAuth(
      () => {
        const current = sessionRef.current;
        return current && !isExpired(current) ? current.token : null;
      },
      () => clear("Your session ended. Please sign in again."),
    );
  }, [clear]);

  // Sign out on the client exactly when the token expires.
  useEffect(() => {
    if (!session) return;
    const ms = new Date(session.expiresAt).getTime() - Date.now() - 30_000;
    const timer = window.setTimeout(() => clear("Your session expired. Please sign in again."), Math.max(ms, 0));
    return () => window.clearTimeout(timer);
  }, [session, clear]);

  const adopt = useCallback((response: TokenResponse): User => {
    const next = sessionFromToken(response);
    saveSession(next);
    sessionRef.current = next;
    setSession(next);
    setSignedOutReason(null);
    setSignedOutDeliberately(false);
    queryClient.removeQueries({ queryKey: ["me"] });
    return next.user;
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(() => ({
    user: session?.user ?? null,
    isAuthenticated: session !== null,
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
        saveSession(next);
        return next;
      });
    },
    adoptToken: (response) => {
      adopt(response);
    },
    forget: () => clear(null),
  }), [session, signedOutReason, signedOutDeliberately, adopt, clear]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
