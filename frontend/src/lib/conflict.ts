/** The saved version a 409 stale_revision carries (null for an older server that only sends the number). */
export function savedVersion<T>(details: unknown): T | null {
  return ((details as { current?: T } | null)?.current ?? null) as T | null;
}
