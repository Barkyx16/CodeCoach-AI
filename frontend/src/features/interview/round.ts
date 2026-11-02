import type { QuestionSummary } from "@/api/types";

export function countWords(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

/** The order a real interview tends to follow: why you, what you know, then harder ground. */
export const ROUND = ["motivation", "knowledge", "situational", "behavioral", "leadership"] as const;

function shuffle<T>(items: T[]): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j]!, out[i]!];
  }
  return out;
}

/**
 * One question of each kind, in interview order, favouring questions not answered yet. Kinds
 * this career has no question for are filled from the rest, so a round always has 5 questions.
 */
export function pickRound(pool: QuestionSummary[], size: number = ROUND.length): QuestionSummary[] {
  const fresh = (q: QuestionSummary) => (q.best_score == null ? 0 : 1);
  const ranked = shuffle(pool).sort((a, b) => fresh(a) - fresh(b));
  const picked: QuestionSummary[] = [];
  for (const kind of ROUND) {
    const q = ranked.find((x) => x.kind === kind && !picked.includes(x));
    if (q) picked.push(q);
  }
  for (const q of ranked) {
    if (picked.length >= size) break;
    if (!picked.includes(q)) picked.push(q);
  }
  return picked.slice(0, size);
}
