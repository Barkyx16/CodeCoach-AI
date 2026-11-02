import { createContext } from "react";

import type { LoginRequest, RegisterRequest, TokenResponse, User } from "@/api/types";

export interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  /** Still checking the refresh cookie on page load; don't redirect to /login yet. */
  isRestoring: boolean;
  /** Why the user was signed out automatically (expired/revoked), for a friendly banner. */
  signedOutReason: string | null;
  /** The user signed out on purpose (logout / deleted account) rather than the session expiring. */
  signedOutDeliberately: boolean;
  login(body: LoginRequest): Promise<User>;
  register(body: RegisterRequest): Promise<User>;
  continueAsGuest(displayName?: string): Promise<User>;
  /** Sign out of this device. */
  logout(): Promise<void>;
  /** Sign out of every device (revokes all sessions server-side). */
  logoutAll(): Promise<void>;
  /** Replace the stored user after a profile change. */
  setUser(user: User): void;
  /** Adopt a new token (e.g. after a password change revokes the old one). */
  adoptToken(response: TokenResponse): void;
  /** Sign out locally without calling the server (e.g. after the account was deleted). */
  forget(): void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
