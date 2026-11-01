import { QueryClient } from "@tanstack/react-query";

import { shouldRetry } from "@/api/queries";

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: shouldRetry, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
}
