/**
 * Thin, typed fetch wrapper.
 *
 * - Base URL comes from VITE_API_BASE_URL (public build-time config; never a secret).
 * - Every non-2xx response is converted into an ApiError carrying the backend's stable
 *   `error.code`, so UI code branches on codes, never on message text.
 * - Network failures become ApiError("network_error") so callers have one error type.
 */
import { diag, diagPath } from "@/lib/diagnostics";
import { clearFailures, recordFailure } from "@/lib/supportLog";

import type { ErrorEnvelope } from "./types";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

/**
 * Seconds to wait from a Retry-After header: either a number of seconds or an HTTP date
 * (RFC 9110). Null when absent or unreadable; never negative.
 */
export function parseRetryAfter(value: string | null | undefined, now: number = Date.now()): number | null {
  const v = (value ?? "").trim();
  if (!v) return null;
  if (/^\d+$/.test(v)) return Number(v);
  if (!/[A-Za-z]/.test(v)) return null; // an HTTP date names its day and month; "-5" isn't one
  const at = Date.parse(v);
  return Number.isNaN(at) ? null : Math.max(0, Math.ceil((at - now) / 1000));
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | null;
  /** How long the server asked us to wait before trying again (a 429 or 503), if it said. */
  readonly retryAfterSeconds: number | null;
  /** When this answer arrived (ms since the epoch): a wait counts from here. */
  readonly receivedAt: number = Date.now();

  constructor(status: number, code: string, message: string, details: unknown = null, requestId: string | null = null,
    retryAfterSeconds: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
    // The body's figure is the more precise one; the header is the standard one (and the only one
    // a proxy or a server without our error envelope sends).
    const fromBody = (details as { retry_after_seconds?: unknown } | null)?.retry_after_seconds;
    this.retryAfterSeconds = typeof fromBody === "number" && fromBody >= 0 ? Math.ceil(fromBody) : retryAfterSeconds;
  }

  get isAuthError(): boolean {
    return this.status === 401;
  }

  /** When the server's wait is over (ms since the epoch), or null if it asked for none. */
  get retryAt(): number | null {
    return this.retryAfterSeconds === null ? null : this.receivedAt + this.retryAfterSeconds * 1000;
  }
}

type TokenGetter = () => string | null;
type UnauthorizedHandler = (error: ApiError) => void;
/**
 * Get a fresh access token from the refresh cookie; null when the session can't continue. Throws
 * an ApiError("network_error") when the server couldn't be reached: the session isn't over then.
 */
type Refresher = () => Promise<string | null>;

let getToken: TokenGetter = () => null;
let onUnauthorized: UnauthorizedHandler = () => {};
let refreshToken: Refresher = async () => null;
/**
 * Which session a request belongs to. It moves on whenever a session starts or ends (sign-in,
 * sign-out, a session that expired) and whenever auth is wired up again. A 401 that comes back for
 * a request of an earlier session isn't about the session open now: it must not refresh (that
 * would sign a signed-out user back in, or resend one account's request as another's) and must
 * not end the current session. Nor is its data: a successful response to a request sent with an
 * earlier session's token is set aside (`session_changed`), so one account's answers or progress
 * can't be shown to, or cached for, the account that signed in next.
 */
let generation = 0;

/** Wired up once by AuthProvider so the client never imports React state directly. */
export function configureAuth(
  tokenGetter: TokenGetter,
  unauthorizedHandler: UnauthorizedHandler,
  refresher: Refresher = async () => null,
): void {
  getToken = tokenGetter;
  onUnauthorized = unauthorizedHandler;
  refreshToken = refresher;
  generation += 1;
}

/** A session started or ended: requests already on their way belong to the previous one. */
export function startAuthGeneration(): void {
  generation += 1;
  clearFailures(); // another session: the earlier one's failures don't belong in this one's report
}

/**
 * The session the cache belongs to right now. A change that writes back to the cache when it
 * answers (putting an optimistic update back after a failure) takes this before it starts and
 * writes back only while `isSameSession` says it's still on: otherwise the previous account's
 * snapshot would land in the cache of the account that signed in next.
 */
export function sessionMark(): number {
  return generation;
}

export function isSameSession(mark: number): boolean {
  return mark === generation;
}

const AUTH_PATH = "/api/v1/auth/";

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
  signal?: AbortSignal;
  /** Send the bearer token if we have one (default true). */
  auth?: boolean;
  /** Let the request finish even if the page is being unloaded (saving on navigation). */
  keepalive?: boolean;
  /** Send this JSON text as the body exactly as it is (a backup file), instead of serializing `body`. */
  rawBody?: string;
  /** Return the body as text (for files such as .ics) instead of parsing JSON. */
  raw?: boolean;
  headers?: Record<string, string>;
  /** W3C trace context of the user action this request belongs to (lib/trace.ts). */
  traceparent?: string;
  /** Never refresh the session or sign out on a 401 (background telemetry). */
  noRefresh?: boolean;
}

export function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(API_BASE_URL + path);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }
  return url.toString();
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  return typeof value === "object" && value !== null && "error" in value &&
    typeof (value as { error: unknown }).error === "object";
}

/**
 * Is the API answering? A cheap GET with no credentials. Used after the network comes back,
 * before spending the one-use refresh cookie: a first request on a connection that died while
 * offline can be resent by the browser, and a resent refresh looks like a stolen cookie.
 */
export async function serverReachable(timeoutMs = 5000): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { cache: "no-store", credentials: "omit", signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return send<T>(path, options, false);
}

async function send<T>(path: string, options: RequestOptions, isRetry: boolean): Promise<T> {
  const { method = "GET", body, query, signal, auth = true } = options;
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  if (body !== undefined || options.rawBody !== undefined) headers["Content-Type"] = "application/json";
  const token = auth ? getToken() : null;
  const sentIn = generation;
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.traceparent) headers.traceparent = options.traceparent;

  const started = performance.now();
  const where = { method, path: diagPath(path), retry: isRetry };
  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: options.rawBody ?? (body === undefined ? undefined : JSON.stringify(body)),
      signal,
      keepalive: options.keepalive,
      // The refresh cookie is path-scoped to /api/v1/auth; only those calls need credentials.
      credentials: path.startsWith(AUTH_PATH) ? "include" : "same-origin",
    });
  } catch (cause) {
    const aborted = cause instanceof DOMException && cause.name === "AbortError";
    diag("http", { ...where, status: 0, outcome: aborted ? "aborted" : "network_error", ms: Math.round(performance.now() - started) });
    if (aborted) throw cause;
    recordFailure({ method, path, status: 0, code: "network_error", request_id: null });
    throw new ApiError(0, "network_error", "Can't reach the CodeCoach server. Check your connection and try again.");
  }
  diag("http", {
    ...where, status: response.status, ms: Math.round(performance.now() - started), requestId: response.headers.get("X-Request-ID"),
    traceId: response.headers.get("X-Trace-ID"),
  });

  if (response.ok && token && sentIn !== generation) {
    // Sent with the token of a session that has since ended or been replaced: what it brings back
    // belongs to that session. (The server may still have done the work; only delivery stops.)
    diag("auth", { event: "stale_response", path: diagPath(path) });
    throw new ApiError(0, "session_changed", "This was sent before you signed in or out, so it was set aside.");
  }
  if (response.status === 204) return undefined as T;

  const text = await response.text();
  if (options.raw && response.ok) return text as T;
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const requestId = response.headers.get("X-Request-ID");
    const retryAfter = parseRetryAfter(response.headers.get("Retry-After"));
    // A refused session check is how "signed out" is learned, not a failure (the report says signed out).
    if (!(response.status === 401 && path.startsWith("/api/v1/auth/refresh"))) {
      recordFailure({ method, path, status: response.status, code: isErrorEnvelope(data) ? data.error.code : "http_error",
        request_id: (isErrorEnvelope(data) ? data.error.request_id : null) ?? requestId });
    }
    const error = isErrorEnvelope(data)
      ? new ApiError(response.status, data.error.code, data.error.message, data.error.details ?? null,
          data.error.request_id ?? requestId, retryAfter)
      : new ApiError(response.status, "http_error", `Request failed with status ${response.status}`, null, requestId,
          retryAfter);
    if (error.status === 401 && token && !options.noRefresh) {
      if (sentIn !== generation) {
        // Sent in a session that has since ended or been replaced: not this session's 401.
        diag("auth", { event: "stale_401", path: diagPath(path) });
        throw error;
      }
      // The access token expired or was revoked: try the refresh cookie once, then retry. If the
      // refresh couldn't reach the server, that network error is thrown instead (still signed in).
      if (!isRetry && !path.startsWith(AUTH_PATH) && (await refreshToken())) {
        if (sentIn === generation) return send<T>(path, options, true);
        diag("auth", { event: "stale_401", path: diagPath(path) });
        throw error;
      }
      // Only the session this request was sent in can end because of it.
      if (sentIn === generation) onUnauthorized(error);
    }
    throw error;
  }
  return data as T;
}
