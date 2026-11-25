import type { NoteFreshness } from "@/api/types";

/** The badge a saved item's source state earns; none when there's nothing to say. */
export function freshnessBadge(f: NoteFreshness | null | undefined): string | null {
  if (!f) return null;
  if (f.state === "needs_review") return "Source updated";
  if (f.state === "unknown") return "Version not known";
  if (f.state === "retired") return "Source retired";
  return null; // current; unavailable is said by the row's own banner
}

/** Items whose source has a newer version that matters, as the server judged it. */
export const sourceUpdated = (f: NoteFreshness | null | undefined) => f?.state === "needs_review";
