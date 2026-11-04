import type { QuestionSummary } from "@/api/types";

import { nextLevel, upNext } from "./upNext";

const q = (id: string, best_score: number | null): QuestionSummary =>
  ({ id, title: id, prompt: `${id}?`, difficulty: "easy", kind: "behavioral", best_score }) as QuestionSummary;

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
