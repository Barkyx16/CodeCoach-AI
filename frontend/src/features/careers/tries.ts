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

/** The answer sent just before `answer` to the same question, if it's listed. */
export function previousTry(newestFirst: InterviewAnswer[], answer: InterviewAnswer): InterviewAnswer | null {
  const i = newestFirst.findIndex((a) => a.id === answer.id);
  if (i >= 0) return newestFirst[i + 1] ?? null;
  // Not listed yet (just sent, list still loading): the newest listed answer came before it.
  return newestFirst.find((a) => a.created_at < answer.created_at) ?? null;
}

export type Comparison =
  | { comparable: true; gained: string[]; lost: string[]; scoreFrom: number; scoreTo: number }
  | { comparable: false; reasons: string[] };

/**
 * Two tries are compared directly only when they were graded the same way: the same version of
 * the question, the same rubric and the same coach, and both long enough to score. Otherwise a
 * score difference could come from the grading, not the answer, so the reasons are given instead.
 */
export function compareTries(before: InterviewAnswer, after: InterviewAnswer): Comparison {
  const reasons: string[] = [];
  if (before.content_version !== after.content_version) {
    reasons.push(`the question was changed in between (version ${before.content_version}, now ${after.content_version})`);
  }
  if (before.rubric_version !== after.rubric_version) {
    reasons.push(`they were graded with different rubrics (${before.rubric_version} and ${after.rubric_version})`);
  }
  if (before.coach !== after.coach) {
    reasons.push(`different coaches graded them (${before.coach} and ${after.coach})`);
  }
  if (before.evidence_level === "insufficient" || after.evidence_level === "insufficient") {
    reasons.push("one of them was too short to score");
  }
  if (reasons.length) return { comparable: false, reasons };
  const had = new Set(before.points.filter((p) => p.covered).map((p) => p.label));
  const has = new Set(after.points.filter((p) => p.covered).map((p) => p.label));
  return {
    comparable: true,
    gained: after.points.filter((p) => p.covered && !had.has(p.label)).map((p) => p.label),
    lost: before.points.filter((p) => p.covered && !has.has(p.label)).map((p) => p.label),
    scoreFrom: before.score,
    scoreTo: after.score,
  };
}

/** The first point a revision could add: the first one not covered, in the rubric's order. */
export function revisionTarget(answer: InterviewAnswer): { label: string; advice: string } | null {
  const missing = answer.points.find((p) => !p.covered);
  return missing ? { label: missing.label, advice: missing.advice } : null;
}
