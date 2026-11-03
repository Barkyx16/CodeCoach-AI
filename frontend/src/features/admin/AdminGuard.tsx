import type { ReactNode } from "react";

import { useAuth } from "@/auth/useAuth";
import { LoadingState } from "@/components/States";
import { NotFoundPage } from "@/app/NotFoundPage";

/** Admin pages look like any missing page to everyone else (the API answers 404 too). */
export function AdminGuard({ children }: { children: ReactNode }) {
  const { user, isRestoring } = useAuth();
  if (isRestoring) return <LoadingState label="Checking access…" />;
  if (!user?.is_admin) return <NotFoundPage />;
  return <>{children}</>;
}
