import { useLocation } from "react-router-dom";

import { appPath } from "@/lib/links";

/**
 * Where a page was opened from, when it was opened from a list that wants it back (e.g. History).
 * `previous`: the page that linked here is the browser's previous entry, so going back restores
 * it exactly (filters, page, scroll). A sender that moves forward through several pages (the
 * practice queue) sets `backVia: "link"`: going back then opens `from` itself, since the previous
 * entry is another item, not the list.
 */
export function useCameFrom(): { from: string; label: string; previous: boolean } | null {
  const state = useLocation().state as { from?: string; fromLabel?: string; backVia?: string } | null;
  const from = appPath(state?.from);
  return from ? { from, label: state?.fromLabel ?? "Back", previous: state?.backVia !== "link" } : null;
}
