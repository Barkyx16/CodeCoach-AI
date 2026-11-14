import type { InterviewAnswer } from "@/api/types";
import { nurseAnswer } from "@/test/fixtures";

import { ANSWERS_LISTED, pointsChange, revisionTarget, tryNumbers } from "./tries";

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

  it("lists what changed in the points covered (whether tries compare is the server's contract)", () => {
    expect(pointsChange(first, second)).toEqual({ gained: [RESULT], lost: [] });
    expect(pointsChange(second, first)).toEqual({ gained: [], lost: [RESULT] });
  });

  it("aims a revision at the first point not covered, in the rubric's order", () => {
    expect(revisionTarget(first)).toEqual({ label: RESULT, advice: "Finish with what happened." });
    expect(revisionTarget(second)).toBeNull();
  });
});
