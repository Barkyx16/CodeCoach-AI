import { QueryClient } from "@tanstack/react-query";

import { shouldRetry } from "@/api/queries";

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      // networkMode "always": requests are attempted even when the browser says it's offline,
      // so they fail fast with a clear "can't reach the server" (and saved offline copies can
      // be used) instead of pausing with an endless spinner.
      queries: { retry: shouldRetry, refetchOnWindowFocus: false, networkMode: "always" },
      // Mutations never pause and replay on reconnect: an answer, a submission or an interview
      // turn is only ever sent when the learner presses the button again.
      mutations: { retry: false, networkMode: "always" },
    },
  });
}
