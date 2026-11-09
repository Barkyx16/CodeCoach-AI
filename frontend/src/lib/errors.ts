import { ApiError } from "@/api/client";

/** Human-friendly title + message for any error, keyed on the backend's stable error codes. */
export function describeError(error: unknown): { title: string; message: string; requestId: string | null } {
  if (error instanceof ApiError) {
    const titles: Record<string, string> = {
      network_error: "You're offline or the server is unreachable",
      not_found: "Not found",
      rate_limited: "Slow down a little",
      account_throttled: "Too many tries",
      invalid_token: "Session ended",
      unauthorized: "Sign in required",
      internal_error: "Something went wrong on our side",
      validation_error: "Check what you entered",
      forbidden: "Not allowed",
      judge_busy: "The code judge is busy",
      judge_unavailable: "The code judge is unavailable",
      execution_disabled: "Code can't run on this server",
      submission_pending: "Your last submission is still being judged",
      server_busy: "The server is busy",
      database_unavailable: "The server can't reach its database",
      ai_request_in_progress: "Another coaching request is still running",
      request_in_progress: "Still being answered",
      idempotency_key_reused: "Already sent with different content",
      session_changed: "You signed in or out meanwhile",
    };
    return { title: titles[error.code] ?? "Request failed", message: error.message, requestId: error.requestId };
  }
  return { title: "Something went wrong", message: error instanceof Error ? error.message : String(error), requestId: null };
}

/**
 * What kind of failure this is, for choosing the way on:
 * - `offline`: no reply came back (the request may or may not have arrived);
 * - `busy`: try again later (429), usually with a wait; `unavailable`: a service is down (503);
 * - `invalid`: the input needs changing (400, 413, 422, or a sign-in's wrong password);
 * - `signed_out`: the session ended; `forbidden`, `not_found`, `conflict`: retrying won't help;
 * - `server`: a fault on our side (other 5xx), which support can trace by its reference.
 */
export type FailureKind =
  | "offline" | "busy" | "unavailable" | "invalid" | "signed_out" | "forbidden" | "not_found" | "conflict" | "server" | "other";

export function failureKind(error: unknown): FailureKind {
  if (!(error instanceof ApiError)) return "other";
  if (error.status === 0) return error.code === "network_error" ? "offline" : "other";
  if (error.status === 429) return "busy";
  if (error.status === 503) return "unavailable";
  if (error.status === 401) return error.code === "invalid_token" || error.code === "unauthorized" ? "signed_out" : "invalid";
  if (error.status === 403) return "forbidden";
  if (error.status === 404) return "not_found";
  if (error.status === 409) return "conflict";
  if (error.status === 400 || error.status === 413 || error.status === 422) return "invalid";
  if (error.status >= 500) return "server";
  return "other";
}

/** A wait, readably: "42 s", "3 min 05 s", "about 23 min", "about 3 h 12 min". */
export function formatWait(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds));
  if (s < 60) return `${s} s`;
  if (s < 600) return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
  if (s < 3600) return `about ${Math.round(s / 60)} min`;
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  return m ? `about ${h} h ${m} min` : `about ${h} h`;
}
