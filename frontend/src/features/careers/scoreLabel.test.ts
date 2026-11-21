import type { ItemStatus } from "@/api/types";

import { isAnswered, scoreLabel } from "./scoreLabel";

const st = (x: Record<string, unknown>) => x as unknown as ItemStatus;

describe("A question's score label", () => {
  it("uses only scoreable answers, and says why an answered question has no score", () => {
    expect(scoreLabel(undefined)).toBe("Not answered");
    expect(scoreLabel(st({ best_score: null, best_scored: null, score_status: null }))).toBe("Not answered");
    expect(scoreLabel(st({ best_score: 0, best_scored: 0, score_status: "scored" }))).toBe("Best score 0"); // a real zero
    expect(scoreLabel(st({ best_score: 35, best_scored: null, score_status: "too_short" }))).toBe("Answered, too short to score");
    expect(scoreLabel(st({ best_score: 50, best_scored: null, score_status: "unknown" }))).toBe("Answered (how it was graded wasn't recorded)");
  });

  it("against an older server (no score_status sent) says answered without a number, not 'Not answered'", () => {
    expect(isAnswered(st({ best_score: 30 }))).toBe(true);
    expect(scoreLabel(st({ best_score: 30 }))).toBe("Answered"); // its raw best may be a capped too-short score
    expect(scoreLabel(st({ best_score: null }))).toBe("Not answered");
  });
});
