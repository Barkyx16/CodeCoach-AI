import type { AttemptConditions, PracticeComparison } from "@/api/types";

/** The labels in one line ("Hint shown, Solution revealed"), as the server gave them. */
export function conditionsSummary(c: AttemptConditions | null | undefined): string | null {
  return c ? c.labels.join(", ") : null;
}

/** The outcome in one line, as History words a submission's (docs/COMPARING_ATTEMPTS.md). */
export const COMPARED_SHORT: Record<PracticeComparison["comparison"]["outcome"], string> = {
  comparable: "Comparable with the one before",
  partially_comparable: "Partly comparable with the one before",
  incompatible: "Not comparable with the one before",
  unknown: "Can't tell whether it compares with the one before",
};
