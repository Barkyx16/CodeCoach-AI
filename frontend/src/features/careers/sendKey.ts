/**
 * The identity of one send of an answer, for a server that keeps at most one saved answer per
 * account and request key (`/capabilities` `answer_request_keys`).
 *
 * A key is reused only for the same logical send: the same account, question, text, story and
 * revised answer, resent after no reply or a failure. Anything else (edited text, another
 * question or account, a new try after a confirmed save) gets a new key. Keys live in memory only:
 * after a reload the old key is gone, so the saved-answer lookup is the only recovery and no
 * duplicate prevention is claimed for it. Nothing here is stored in the browser.
 */
export interface PendingSend {
  key: string;
  signature: string;
}

export function sendSignature(parts: {
  account: string; track: string; questionId: string; answer: string; storyId: string | null; revisesAnswerId: string | null;
  followsUpAnswerId?: string | null;
}): string {
  // A follow-up's link is added only when there is one, so every other send keeps its signature.
  return JSON.stringify([parts.account, parts.track, parts.questionId, parts.answer, parts.storyId, parts.revisesAnswerId,
    ...(parts.followsUpAnswerId ? [parts.followsUpAnswerId] : [])]);
}

function newKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** The key for this send: the pending one if it's the same send, else a new one. */
export function keyFor(pending: PendingSend | null, signature: string, make: () => string = newKey): PendingSend {
  return pending && pending.signature === signature ? pending : { key: make(), signature };
}
