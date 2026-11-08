/**
 * The last few API requests that failed in this session, for the support report (always on, in
 * production too, unlike lib/diagnostics). Kept in memory only, and only identifiers: method, the
 * path with record ids masked and no query string, status, error code, and the server's request
 * id. Never a body, header, token or message. Emptied whenever the session changes (sign-in,
 * sign-out, another account), so one account's failures never appear in another's report.
 */
export interface FailedRequest {
  at: string; // ISO time
  method: string;
  path: string;
  status: number; // 0: no reply came back
  code: string;
  request_id: string | null;
}

const MAX = 5;
let failures: FailedRequest[] = [];

/**
 * A path that names a route, not a record: ids (UUIDs, long hex or random-looking tokens, numbers)
 * and anything that looks like an email address become ":id"; the query and #fragment are dropped.
 */
export function maskPath(path: string): string {
  const bare = (path.split(/[?#]/)[0] ?? "") || "/";
  return bare.split("/").map((segment) => {
    if (!segment) return segment;
    if (/^\d+$/.test(segment) || /@|%40/i.test(segment)) return ":id"; // a number, or something like an address
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment)) return ":id";
    if (segment.length >= 16 && /\d/.test(segment) && /^[A-Za-z0-9_-]+$/.test(segment)) return ":id";
    return segment.slice(0, 60);
  }).join("/");
}

export function recordFailure(entry: Omit<FailedRequest, "at" | "path"> & { path: string }): void {
  failures = [...failures, { ...entry, path: maskPath(entry.path), at: new Date().toISOString() }].slice(-MAX);
}

export function recentFailures(): FailedRequest[] {
  return failures.map((f) => ({ ...f }));
}

export function clearFailures(): void {
  failures = [];
}
