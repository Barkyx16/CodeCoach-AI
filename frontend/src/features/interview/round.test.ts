import type { QuestionSummary } from "@/api/types";

import { pickRound } from "./round";

const q = (id: string, kind: string, best_score: number | null = null): QuestionSummary =>
  ({ id, title: id, prompt: id, difficulty: "easy", kind, best_score });

describe("pickRound", () => {
  it("asks one of each kind, in interview order", () => {
    const pool = ["leadership", "behavioral", "motivation", "situational", "knowledge"].flatMap((k) => [q(`${k}-a`, k), q(`${k}-b`, k)]);
    expect(pickRound(pool).map((x) => x.kind)).toEqual(["motivation", "knowledge", "situational", "behavioral", "leadership"]);
  });

  it("prefers questions not answered yet", () => {
    const pool = [q("old", "motivation", 80), q("new", "motivation")];
    for (let i = 0; i < 20; i++) expect(pickRound(pool, 1)[0]!.id).toBe("new");
  });

  it("fills missing kinds from the rest and never repeats a question", () => {
    const pool = [q("k1", "knowledge"), q("k2", "knowledge"), q("k3", "knowledge"), q("b1", "behavioral")];
    const round = pickRound(pool);
    expect(round).toHaveLength(4);
    expect(new Set(round.map((x) => x.id)).size).toBe(4);
  });
});
