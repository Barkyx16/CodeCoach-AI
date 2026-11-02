import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { LoadingState } from "@/components/States";

import { useAuth } from "./useAuth";

/**
 * Route guard. Signed-out visitors go to /login and come back afterwards; someone who just
 * signed out on purpose (logout, deleted account) goes home instead of being asked to log in.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isRestoring, signedOutDeliberately } = useAuth();
  const location = useLocation();
  if (!isAuthenticated && isRestoring) return <LoadingState label="Restoring your session…" />;
  if (!isAuthenticated) {
    if (signedOutDeliberately) return <Navigate to="/" replace />;
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return <>{children}</>;
}
