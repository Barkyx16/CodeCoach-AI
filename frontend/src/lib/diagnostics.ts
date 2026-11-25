/**
 * Breadcrumbs for diagnosing rare stalls in development and browser tests.
 *
 * Off in production builds. When on, it keeps the last few hundred events in memory
 * (`window.__ccDiag`) for a test harness to read after a failure. It records identifiers,
 * statuses and timings only: never request or response bodies, answers, tokens, cookies or
 * headers. Paths are recorded without their query string.
 */

export type DiagValue = string | number | boolean | null;
export interface DiagEvent {
  t: number; // ms since page load
  kind: string;
  [field: string]: DiagValue;
}

const MAX_EVENTS = 300;
const enabled = import.meta.env.DEV || import.meta.env.MODE === "test";

declare global {
  interface Window {
    __ccDiag?: DiagEvent[];
  }
}

export function diagEnabled(): boolean {
  return enabled && typeof window !== "undefined";
}

/** Record one event. Undefined fields are dropped; strings are capped so nothing large is kept. */
export function diag(kind: string, fields: Record<string, DiagValue | undefined> = {}): void {
  if (!diagEnabled()) return;
  const event: DiagEvent = { t: Math.round(performance.now()), kind };
  for (const [key, value] of Object.entries(fields)) {
    if (value === undefined) continue;
    event[key] = typeof value === "string" ? value.slice(0, 120) : value;
  }
  const log = (window.__ccDiag ??= []);
  log.push(event);
  if (log.length > MAX_EVENTS) log.splice(0, log.length - MAX_EVENTS);
}

/** A path for the log: no query string (it can carry search terms). */
export function diagPath(path: string): string {
  return path.split("?")[0] ?? path;
}
