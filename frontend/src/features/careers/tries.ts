import type { InterviewAnswer } from "@/api/types";

/** `GET …/questions/{id}/answers` returns at most this many, newest first. */
export const ANSWERS_LISTED = 20;

/**
 * Try numbers (1 = the first answer to this question), from this account's answers, newest first.
 * Only when the list is complete: with ANSWERS_LISTED or more, the first tries may be cut off, so
 * no numbers are given rather than wrong ones.
 */
export function tryNumbers(newestFirst: InterviewAnswer[]): Map<string, number> | null {
  if (newestFirst.length >= ANSWERS_LISTED) return null;
  return new Map(newestFirst.map((a, i) => [a.id, newestFirst.length - i]));
}

/**
 * What changed in the points covered between two tries. Whether two tries compare at all is never
 * decided here: the server's comparison contract decides it (docs/COMPARING_ATTEMPTS.md), and this
 * is used only when it says what was written compares.
 */
export function pointsChange(before: InterviewAnswer, after: InterviewAnswer): { gained: string[]; lost: string[] } {
  const had = new Set(before.points.filter((p) => p.covered).map((p) => p.label));
  const has = new Set(after.points.filter((p) => p.covered).map((p) => p.label));
  return {
    gained: after.points.filter((p) => p.covered && !had.has(p.label)).map((p) => p.label),
    lost: before.points.filter((p) => p.covered && !has.has(p.label)).map((p) => p.label),
  };
}

/** The first point a revision could add: the first one not covered, in the rubric's order. */
export function revisionTarget(answer: InterviewAnswer): { label: string; advice: string } | null {
  const missing = answer.points.find((p) => !p.covered);
  return missing ? { label: missing.label, advice: missing.advice } : null;
}
