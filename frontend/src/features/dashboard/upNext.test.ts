import type { QuestionSummary } from "@/api/types";

import { nextLevel, upNext } from "./upNext";

/** A question with a scoreable best (or unanswered when null). */
const q = (id: string, best_score: number | null): QuestionSummary =>
  ({ id, title: id, prompt: `${id}?`, difficulty: "easy", kind: "behavioral", best_score, best_scored: best_score,
    score_status: best_score === null ? null : "scored" }) as QuestionSummary;
/** Answered, but every answer too short to score (its stored score is capped) or not recorded. */
const unscored = (id: string, status: "too_short" | "unknown"): QuestionSummary =>
  ({ id, title: id, prompt: `${id}?`, difficulty: "easy", kind: "behavioral", best_score: 30, best_scored: null, score_status: status }) as QuestionSummary;

describe("Up next", () => {
  it("first use: the easy level, unanswered questions in library order", () => {
    expect(nextLevel({})).toBe("easy");
    const r = upNext([q("a", null), q("b", null), q("c", null), q("d", null)], 4);
    expect(r.fresh.map((x) => x.id)).toEqual(["a", "b", "c"]);
    expect(r.retry).toEqual([]);
    expect(r.levelDone).toBe(false);
  });

  it("moves up a level after ten answered questions there, and stays on hard at the end", () => {
    expect(nextLevel({ easy: 9 })).toBe("easy");
    expect(nextLevel({ easy: 10 })).toBe("medium");
    expect(nextLevel({ easy: 12, medium: 10, hard: 3 })).toBe("hard");
    expect(nextLevel({ easy: 10, medium: 10, hard: 10 })).toBe("hard");
  });

  it("puts weak answers first (below 70), keeps library order for ties, and caps both lists", () => {
    const r = upNext([q("a", 90), q("b", 40), q("c", null), q("d", 69), q("e", 10), q("f", 70), q("g", null)], 7);
    expect(r.retry.map((x) => x.id)).toEqual(["b", "d"]); // e is the third weak one: not shown
    expect(r.fresh.map((x) => x.id)).toEqual(["c", "g"]);
  });

  it("suggests trying again where every answer was too short to score, without treating it as a score or as new", () => {
    const r = upNext([q("a", 90), unscored("b", "too_short"), q("c", null), unscored("d", "unknown")], 4);
    expect(r.retry.map((x) => x.id)).toEqual(["b"]); // no score: a retry, not a "best score of 30"
    expect(r.fresh.map((x) => x.id)).toEqual(["c"]); // b and d are answered, so they aren't new
  });

  it("claims the level is done only when every question at the level was seen", () => {
    const all = [q("a", 90), q("b", 75)];
    expect(upNext(all, 2).levelDone).toBe(true);
    // The list held 2 of 5 questions: nothing to suggest from it, but the level isn't done.
    const seen = upNext(all, 5);
    expect(seen.levelDone).toBe(false);
    expect(seen.partial).toBe(true);
    // An unknown total never allows the claim either.
    expect(upNext(all, undefined).levelDone).toBe(false);
  });
});
