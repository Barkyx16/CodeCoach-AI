import type { TokenResponse, User } from "@/api/types";
import { storage } from "@/lib/storage";

const KEY = "codecoach.session.v1";

export interface Session {
  token: string;
  expiresAt: string;
  user: User;
}

export function sessionFromToken(response: TokenResponse): Session {
  return { token: response.access_token, expiresAt: response.expires_at, user: response.user };
}

export function isExpired(session: Session, now: number = Date.now()): boolean {
  // 30s safety margin so we never send a token that expires mid-request.
  return new Date(session.expiresAt).getTime() - 30_000 <= now;
}

export function loadSession(): Session | null {
  const raw = storage.get(KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Session;
    if (!parsed.token || !parsed.expiresAt || !parsed.user || isExpired(parsed)) {
      storage.remove(KEY);
      return null;
    }
    return parsed;
  } catch {
    storage.remove(KEY);
    return null;
  }
}

export function saveSession(session: Session | null): void {
  if (session) storage.set(KEY, JSON.stringify(session));
  else storage.remove(KEY);
}
