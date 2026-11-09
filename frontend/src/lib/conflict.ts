/** The saved version a 409 stale_revision carries (null for an older server that only sends the number). */
export function savedVersion<T>(details: unknown): T | null {
  return ((details as { current?: T } | null)?.current ?? null) as T | null;
}

/**
 * A save the server had already accepted under its key (its first reply was lost: Volume 8,
 * prompt 3). `newer`: the record was changed after that save, so what came back is that newer
 * version, not the learner's: compare, don't replace the page with it. Null for an ordinary save.
 */
export function recoveredSave(saved: { save_replay?: { accepted_revision: number; current_revision: number } | null }):
  { accepted: number; current: number; newer: boolean } | null {
  const r = saved.save_replay;
  return r ? { accepted: r.accepted_revision, current: r.current_revision, newer: r.current_revision > r.accepted_revision } : null;
}
