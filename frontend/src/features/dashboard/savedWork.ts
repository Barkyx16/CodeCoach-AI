/** Work saved in this browser that "Continue where you left off" can offer. Reads only; never edits. */

export const answerDraftKey = (userId: string, track: string, questionId: string) =>
  `codecoach.answer.${userId}.${track}.${questionId}`;

export interface LocalWork {
  answerDraft: { track: string; questionId: string; words: number } | null;
  codingDraft: { slug: string } | null;
}

function keys(): string[] {
  try {
    return Array.from({ length: window.localStorage.length }, (_, i) => window.localStorage.key(i) ?? "");
  } catch {
    return [];
  }
}

function value(key: string): string {
  try {
    return window.localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

export function findLocalWork(userId: string): LocalWork {
  let answerDraft: LocalWork["answerDraft"] = null;
  let codingDraft: LocalWork["codingDraft"] = null;
  const answerPrefix = `codecoach.answer.${userId}.`;
  const codePrefix = `codecoach.draft.v1.${userId}.`;
  for (const key of keys()) {
    if (!answerDraft && key.startsWith(answerPrefix)) {
      const text = value(key).trim();
      const [track, questionId] = key.slice(answerPrefix.length).split(".");
      if (text && track && questionId) answerDraft = { track, questionId, words: text.split(/\s+/).length };
    }
    // Coding drafts are stored only when they differ from the starter code. Interview editors are excluded.
    if (!codingDraft && key.startsWith(codePrefix)) {
      const slug = key.slice(codePrefix.length);
      if (slug && !slug.startsWith("interview-") && value(key)) codingDraft = { slug };
    }
  }
  return { answerDraft, codingDraft };
}
