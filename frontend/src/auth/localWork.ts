/**
 * Private work kept on this device, per account: unsent answers, code drafts, interview-round
 * drafts and note recovery copies. Signing out deletes the signed-out account's copies (after a
 * warning when there are any), so the next person on a shared device can't read them. Device
 * preferences (display, editor, voice) and public "Saved for offline" copies are kept: they
 * aren't account data. See docs/OFFLINE.md, and docs/YOUR_DATA.md for "Your data", which lists
 * these copies and removes the ones the learner picks.
 */

import { recentKey } from "@/app/commands";
import { forgetRemovals, readCopy } from "@/lib/deviceCopies";

function keys(): string[] {
  try {
    return Array.from({ length: window.localStorage.length }, (_, i) => window.localStorage.key(i) ?? "");
  } catch {
    return [];
  }
}

/** Where each kind of copy's key starts. Interview-keyed kinds don't name the account: only the
 * interview's owner can open them. What each kind is, for "Your data", is in
 * features/privacy/copyKinds.ts (loaded with that page, not with every page). Every unsent-text
 * draft in the app must be listed here (a test lists the prefixes the features use). */
export const COPY_PREFIXES: { id: string; prefix: (userId: string) => string; interview?: boolean }[] = [
  { id: "answer", prefix: (u) => `codecoach.answer.${u}.` },
  { id: "code", prefix: (u) => `codecoach.draft.v1.${u}.` },
  { id: "note", prefix: (u) => `note-draft:${u}:` },
  { id: "note-capture", prefix: (u) => `note-capture:${u}:` },
  { id: "learn", prefix: (u) => `learn-draft:${u}:` },
  { id: "story", prefix: (u) => `story-draft:${u}:` },
  { id: "whiteboard", prefix: (u) => `whiteboard-draft:${u}:` },
  { id: "reflection", prefix: (u) => `reflection-draft:${u}:` },
  { id: "drill", prefix: (u) => `drill-draft:${u}:` },
  { id: "form", prefix: (u) => `form-draft:${u}:` },
  { id: "debug-notes", prefix: (u) => `debug-notes:${u}:` },
  { id: "code-review", prefix: (u) => `code-review-draft:${u}:` },
  { id: "test-design", prefix: (u) => `test-design-draft:${u}:` },
  { id: "work-sample", prefix: (u) => `work-sample-draft:${u}:` },
  { id: "compare", prefix: (u) => `compare-draft:${u}:` },
  { id: "queue", prefix: (u) => `scenario-queue-draft:${u}:` },
  { id: "offer-rehearsal", prefix: (u) => `offer-rehearsal-draft:${u}:` },
  { id: "offer-compare", prefix: (u) => `offer-compare-draft:${u}:` },
  { id: "application-notes", prefix: (u) => `codecoach.appnotes.v1.${u}.` },
  { id: "round", prefix: () => "codecoach.round.", interview: true },
  { id: "interview-message", prefix: () => "codecoach.interview-message.", interview: true },
  { id: "retry", prefix: () => "codecoach.retry.", interview: true },
];


/** Keys that hold this account's private work. Interview round, chat and retry drafts are keyed
 * by the interview (only its owner can open it), not the account; they're cleared with whoever
 * signs out on this device. */
export function localWorkKeys(userId: string): string[] {
  const prefixes = COPY_PREFIXES.map((k) => k.prefix(userId));
  return keys().filter((k) => prefixes.some((p) => k.startsWith(p)));
}

/** How many unsent items this account has on this device (empty values don't count). */
export function countLocalWork(userId: string): number {
  return localWorkKeys(userId).filter((k) => Boolean(readCopy(k)?.trim())).length;
}

export function clearLocalWork(userId: string): void {
  // Also the pages this account last opened from the command palette (ids only, not counted as
  // unsent work above): the next person on this device doesn't inherit them.
  for (const k of [...localWorkKeys(userId), recentKey(userId)]) {
    try {
      window.localStorage.removeItem(k);
    } catch {
      /* storage blocked: nothing was kept */
    }
  }
  forgetRemovals(); // which copies were removed on purpose: ids and times, for this account's pages
  clearListMemory();
}

/**
 * This tab's list positions and the items opened from them (hooks/useScrollMemory.ts): which note
 * or application was opened is that account's, so it goes when the account signs out here, and the
 * next account's Back starts its lists at the top.
 */
export function clearListMemory(): void {
  try {
    const stale = Array.from({ length: window.sessionStorage.length }, (_, i) => window.sessionStorage.key(i) ?? "")
      .filter((k) => k.startsWith("scroll:") || k.startsWith("focus:scroll:"));
    for (const k of stale) window.sessionStorage.removeItem(k);
  } catch {
    /* storage blocked: nothing was kept */
  }
}
