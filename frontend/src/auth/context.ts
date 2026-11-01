import { createContext } from "react";

import type { LoginRequest, RegisterRequest, User } from "@/api/types";

export interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  /** Why the user was signed out automatically (expired/revoked), for a friendly banner. */
  signedOutReason: string | null;
  login(body: LoginRequest): Promise<User>;
  register(body: RegisterRequest): Promise<User>;
  continueAsGuest(displayName?: string): Promise<User>;
  logout(): Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
