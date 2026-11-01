import { ApiError } from "@/api/client";

/** Human-friendly title + message for any error, keyed on the backend's stable error codes. */
export function describeError(error: unknown): { title: string; message: string; requestId: string | null } {
  if (error instanceof ApiError) {
    const titles: Record<string, string> = {
      network_error: "You're offline or the server is unreachable",
      not_found: "Not found",
      rate_limited: "Slow down a little",
      invalid_token: "Session ended",
      unauthorized: "Sign in required",
      internal_error: "Something went wrong on our side",
    };
    return { title: titles[error.code] ?? "Request failed", message: error.message, requestId: error.requestId };
  }
  return { title: "Something went wrong", message: error instanceof Error ? error.message : String(error), requestId: null };
}
