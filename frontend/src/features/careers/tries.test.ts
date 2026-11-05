import type { InterviewAnswer } from "@/api/types";
import { nurseAnswer } from "@/test/fixtures";

import { ANSWERS_LISTED, compareTries, previousTry, revisionTarget, tryNumbers } from "./tries";

const SCENE = "Sets the scene: where you were and what was at stake";
const RESULT = "Shares a result, ideally with a number";

function answer(id: string, at: string, covered: Record<string, boolean>, extra: Partial<InterviewAnswer> = {}): InterviewAnswer {
  return {
    ...nurseAnswer, id, created_at: at,
    points: [
      { label: SCENE, covered: covered[SCENE] ?? false, advice: "Open with context." },
      { label: RESULT, covered: covered[RESULT] ?? false, advice: "Finish with what happened." },
    ],
    ...extra,
  };
}

const first = answer("a1", "2026-11-01T09:00:00Z", { [SCENE]: true }, { score: 58 });
const second = answer("a2", "2026-11-02T09:00:00Z", { [SCENE]: true, [RESULT]: true }, { score: 81 });

describe("Tries at one question", () => {
  it("numbers tries from the first, when the list is complete", () => {
    expect(tryNumbers([second, first])).toEqual(new Map([["a2", 2], ["a1", 1]]));
  });

  it("gives no numbers when the list may be missing the first tries", () => {
    const many = Array.from({ length: ANSWERS_LISTED }, (_, i) => answer(`x${i}`, `2026-10-${String(30 - i).padStart(2, "0")}T00:00:00Z`, {}));
    expect(tryNumbers(many)).toBeNull();
  });

  it("finds the try before an answer, listed or just sent", () => {
    expect(previousTry([second, first], second)).toBe(first);
    expect(previousTry([second, first], first)).toBeNull();
    const justSent = answer("a3", "2026-11-03T09:00:00Z", {});
    expect(previousTry([second, first], justSent)).toBe(second);
  });

  it("compares tries graded the same way by the points each covered", () => {
    expect(compareTries(first, second)).toEqual({ comparable: true, gained: [RESULT], lost: [], scoreFrom: 58, scoreTo: 81 });
    expect(compareTries(second, first)).toEqual({ comparable: true, gained: [], lost: [RESULT], scoreFrom: 81, scoreTo: 58 });
  });

  it("doesn't compare tries graded differently, and says why", () => {
    const newerRubric = { ...second, rubric_version: "v8" };
    expect(compareTries(first, newerRubric)).toEqual({ comparable: false, reasons: ["they were graded with different rubrics (v1 and v8)"] });
    const changedQuestion = { ...second, content_version: 2 };
    expect(compareTries(first, changedQuestion)).toMatchObject({ comparable: false, reasons: ["the question was changed in between (version 1, now 2)"] });
    const otherCoach = { ...second, coach: "claude" };
    expect(compareTries(first, otherCoach)).toMatchObject({ comparable: false, reasons: [expect.stringContaining("different coaches")] });
    const tooShort = { ...first, evidence_level: "insufficient" as const };
    expect(compareTries(tooShort, second)).toMatchObject({ comparable: false, reasons: ["one of them was too short to score"] });
    const unrecorded = { ...first, evidence_level: "unknown" as const };
    expect(compareTries(unrecorded, second)).toMatchObject({ comparable: false, reasons: ["how one of them was graded wasn't recorded"] });
  });

  it("aims a revision at the first point not covered, in the rubric's order", () => {
    expect(revisionTarget(first)).toEqual({ label: RESULT, advice: "Finish with what happened." });
    expect(revisionTarget(second)).toBeNull();
  });
});
