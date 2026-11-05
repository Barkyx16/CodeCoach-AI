/**
 * Activities the learner explicitly added to Today, kept for this tab (sessionStorage) by plan
 * version and time budget: only plan item ids, no learner text. A new plan version (after a
 * completion, a swap or a goal change) or another budget starts with none added.
 */
const KEY = "codecoach.today.added.v1";

export function addedFor(scope: string): string[] {
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(KEY) ?? "null") as { scope?: unknown; ids?: unknown } | null;
    if (!saved || saved.scope !== scope || !Array.isArray(saved.ids)) return [];
    return saved.ids.filter((id): id is string => typeof id === "string");
  } catch {
    return [];
  }
}

export function saveAdded(scope: string, ids: string[]): void {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify({ scope, ids }));
  } catch {
    /* kept for this page view only */
  }
}
