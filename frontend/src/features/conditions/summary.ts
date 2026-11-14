import type { AttemptConditions } from "@/api/types";

/** The labels in one line ("Hint shown, Solution revealed"), as the server gave them. */
export function conditionsSummary(c: AttemptConditions | null | undefined): string | null {
  return c ? c.labels.join(", ") : null;
}
