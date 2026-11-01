/**
 * Thin, typed fetch wrapper.
 *
 * - Base URL comes from VITE_API_BASE_URL (public build-time config; never a secret).
 * - Every non-2xx response is converted into an ApiError carrying the backend's stable
 *   `error.code`, so UI code branches on codes, never on message text.
 * - Network failures become ApiError("network_error") so callers have one error type.
 */
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

let getToken: TokenGetter = () => null;
let onUnauthorized: UnauthorizedHandler = () => {};

/** Wired up once by AuthProvider so the client never imports React state directly. */
export function configureAuth(tokenGetter: TokenGetter, unauthorizedHandler: UnauthorizedHandler): void {
  getToken = tokenGetter;
  onUnauthorized = unauthorizedHandler;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
  signal?: AbortSignal;
  /** Send the bearer token if we have one (default true). */
  auth?: boolean;
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

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, signal, auth = true } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = auth ? getToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(0, "network_error", "Can't reach the CodeCoach server. Check your connection and try again.");
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
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
    if (error.status === 401 && token) onUnauthorized(error);
    throw error;
  }
  return data as T;
}
