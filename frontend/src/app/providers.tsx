import { type QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { AuthProvider } from "@/auth/AuthProvider";
import { EditorPreferencesProvider } from "@/features/settings/EditorPreferencesProvider";

export function AppProviders({ children, queryClient }: { children: ReactNode; queryClient: QueryClient }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider><EditorPreferencesProvider>{children}</EditorPreferencesProvider></AuthProvider>
    </QueryClientProvider>
  );
}
