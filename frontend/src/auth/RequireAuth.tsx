import type { ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";

import { LoadingState } from "@/components/States";

import { useAuth } from "./useAuth";

/**
 * Route guard. Signed-out visitors go to /login and come back afterwards; someone who just
 * signed out on purpose (logout, deleted account) goes home instead of being asked to log in.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isRestoring, signedOutDeliberately, offlineUser } = useAuth();
  const location = useLocation();
  if (!isAuthenticated && isRestoring) return <LoadingState label="Restoring your session…" />;
  if (!isAuthenticated && offlineUser) {
    // Offline: the session couldn't be checked. Not a sign-in problem, so don't send them to /login.
    return (
      <div className="page">
        <div className="page__header"><div>
          <p className="eyebrow">OFFLINE</p>
          <h1 className="page__title">This page needs a connection</h1>
          <p className="page__subtitle">It shows your account's data, which isn't kept on this device. It will load when you're back online.</p>
        </div></div>
        <p><Link to="/offline">See what's saved on this device</Link></p>
      </div>
    );
  }
  if (!isAuthenticated) {
    if (signedOutDeliberately) return <Navigate to="/" replace />;
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return <>{children}</>;
}
