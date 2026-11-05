import type { Career } from "@/api/types";

/** Lowercase, without accents, so "cafe" finds "Café". */
function fold(text: string): string {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

/**
 * Jobs matching what was typed, best first: every word typed must start a word of the title or
 * the industry ("reg nur" finds Registered Nurse). Titles that start with it come first, then a
 * title word that does, then an industry match; ties keep the catalogue's order.
 */
export function matchCareers(careers: Career[], query: string): Career[] {
  const words = fold(query).split(/[^a-z0-9]+/).filter(Boolean);
  if (!words.length) return careers;
  const scored: { career: Career; score: number; index: number }[] = [];
  careers.forEach((career, index) => {
    const title = fold(career.title);
    const titleWords = title.split(/[^a-z0-9]+/).filter(Boolean);
    const categoryWords = fold(career.category).split(/[^a-z0-9]+/).filter(Boolean);
    let score = 0;
    for (const word of words) {
      if (titleWords.some((w) => w.startsWith(word))) score += 2;
      else if (categoryWords.some((w) => w.startsWith(word))) score += 1;
      else return; // every word must match somewhere
    }
    if (title.startsWith(fold(query).trim())) score += 3;
    scored.push({ career, score, index });
  });
  return scored.sort((a, b) => b.score - a.score || a.index - b.index).map((s) => s.career);
}
