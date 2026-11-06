import type { TokenResponse, User } from "@/api/types";
import { storage } from "@/lib/storage";

/**
 * The signed-in session lives in memory only. The access token is short-lived (15 min); a
 * page reload restores the session from the HttpOnly refresh cookie (POST /auth/refresh),
 * which page scripts can't read. Nothing about the session is written to localStorage.
 */
export interface Session {
  token: string;
  expiresAt: string;
  user: User;
}

/** Where sessions used to be stored, before refresh cookies. Removed on startup. */
export const LEGACY_SESSION_KEY = "codecoach.session.v1";

export function sessionFromToken(response: TokenResponse): Session {
  return { token: response.access_token, expiresAt: response.expires_at, user: response.user };
}

export function isExpired(session: Session, now: number = Date.now()): boolean {
  // 30s safety margin so we never send a token that expires mid-request.
  return new Date(session.expiresAt).getTime() - 30_000 <= now;
}

/** Milliseconds until the session should be refreshed (a minute before the token expires). */
export function refreshDelay(session: Session, now: number = Date.now()): number {
  return Math.max(new Date(session.expiresAt).getTime() - 60_000 - now, 0);
}

export function forgetLegacySession(): void {
  storage.remove(LEGACY_SESSION_KEY);
}
