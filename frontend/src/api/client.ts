/**
 * Thin, typed fetch wrapper.
 *
 * - Base URL comes from VITE_API_BASE_URL (public build-time config; never a secret).
 * - Every non-2xx response is converted into an ApiError carrying the backend's stable
 *   `error.code`, so UI code branches on codes, never on message text.
 * - Network failures become ApiError("network_error") so callers have one error type.
 */
import { diag, diagPath } from "@/lib/diagnostics";

import type { ErrorEnvelope } from "./types";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, details: unknown = null, requestId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  get isAuthError(): boolean {
    return this.status === 401;
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
 * not end the current session.
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
    throw new ApiError(0, "network_error", "Can't reach the CodeCoach server. Check your connection and try again.");
  }
  diag("http", {
    ...where, status: response.status, ms: Math.round(performance.now() - started), requestId: response.headers.get("X-Request-ID"),
    traceId: response.headers.get("X-Trace-ID"),
  });

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
    const error = isErrorEnvelope(data)
      ? new ApiError(response.status, data.error.code, data.error.message, data.error.details ?? null,
          data.error.request_id ?? requestId)
      : new ApiError(response.status, "http_error", `Request failed with status ${response.status}`, null, requestId);
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
