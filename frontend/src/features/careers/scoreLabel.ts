import type { ItemStatus } from "@/api/types";

/**
 * A question's status line from the learner's answers. Scores only from answers long enough to
 * score (`best_scored`); an answered question without one says why, never shows zero or a capped
 * number. An older server sends no `score_status` at all: then an answer is known only from
 * `best_score`, and which answers could be scored isn't known, so no number is shown.
 */
export function isAnswered(st: ItemStatus | undefined): boolean {
  if (!st) return false;
  if (st.score_status === undefined) return st.best_score != null; // an older server's shape
  return !!st.score_status;
}

export function scoreLabel(st: ItemStatus | undefined): string {
  if (!isAnswered(st)) return "Not answered";
  if (st!.score_status === undefined) return "Answered";
  if (st!.best_scored != null) return `Best score ${st!.best_scored}`;
  return st!.score_status === "too_short" ? "Answered, too short to score" : "Answered (how it was graded wasn't recorded)";
}
