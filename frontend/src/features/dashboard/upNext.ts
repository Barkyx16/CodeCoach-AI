import type { Difficulty, QuestionSummary } from "@/api/types";

/**
 * "Up next" on a career dashboard: a fixed, explainable rule over the learner's own best scores.
 * No model and no profile: the same answers always give the same suggestions.
 *
 * - Level: the first of easy, medium, hard with fewer than LEVEL_UP_AFTER answered questions
 *   (each question counts once, however many tries); hard once all three have that many.
 * - Within that level, in library order: up to MAX_RETRY answered questions whose best score is
 *   below RETRY_BELOW (scores only from answers long enough to score), or whose answers were all
 *   too short to score, then up to MAX_NEW questions not answered yet.
 */
export const LEVELS: Difficulty[] = ["easy", "medium", "hard"];
export const LEVEL_UP_AFTER = 10;
export const RETRY_BELOW = 70;
const MAX_RETRY = 2;
const MAX_NEW = 3;

export function nextLevel(answered: Partial<Record<string, number>>): Difficulty {
  return LEVELS.find((l) => (answered[l] ?? 0) < LEVEL_UP_AFTER) ?? "hard";
}

export interface UpNext {
  retry: QuestionSummary[];
  fresh: QuestionSummary[];
  /** True only when every question at the level was looked at and all are answered at or above the bar. */
  levelDone: boolean;
  /** Fewer questions were listed than the level holds, so "all done" can't be claimed. */
  partial: boolean;
}

/** `items`: the level's questions as listed (library order); `levelTotal`: how many the level holds. */
export function upNext(items: QuestionSummary[], levelTotal: number | undefined): UpNext {
  const retry = items.filter((q) => (q.best_scored != null && q.best_scored < RETRY_BELOW) || q.score_status === "too_short").slice(0, MAX_RETRY);
  const fresh = items.filter((q) => q.best_score == null && !q.score_status).slice(0, MAX_NEW);
  const partial = levelTotal === undefined || items.length < levelTotal;
  return { retry, fresh, levelDone: retry.length + fresh.length === 0 && !partial, partial };
}
