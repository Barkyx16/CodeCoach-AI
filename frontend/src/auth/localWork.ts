/**
 * Private work kept on this device, per account: unsent answers, code drafts, interview-round
 * drafts and note recovery copies. Signing out deletes the signed-out account's copies (after a
 * warning when there are any), so the next person on a shared device can't read them. Device
 * preferences (display, editor, voice) and public "Saved for offline" copies are kept: they
 * aren't account data. See docs/OFFLINE.md.
 */

import { recentKey } from "@/app/commands";

function keys(): string[] {
  try {
    return Array.from({ length: window.localStorage.length }, (_, i) => window.localStorage.key(i) ?? "");
  } catch {
    return [];
  }
}

/** Keys that hold this account's private work. Interview round, chat and retry drafts are keyed
 * by the interview (only its owner can open it), not the account; they're cleared with whoever
 * signs out on this device. Every unsent-text draft in the app must be listed here (a test lists
 * the prefixes the features use). */
export function localWorkKeys(userId: string): string[] {
  const prefixes = [
    `codecoach.answer.${userId}.`,
    `codecoach.draft.v1.${userId}.`,
    `note-draft:${userId}:`,
    `note-capture:${userId}:`,
    `learn-draft:${userId}:`,
    `story-draft:${userId}:`,
    `whiteboard-draft:${userId}:`,
    `reflection-draft:${userId}:`,
    `drill-draft:${userId}:`,
    `form-draft:${userId}:`,
    `debug-notes:${userId}:`,
    `code-review-draft:${userId}:`,
    `test-design-draft:${userId}:`,
    `work-sample-draft:${userId}:`,
    `compare-draft:${userId}:`,
    `scenario-queue-draft:${userId}:`,
    `offer-rehearsal-draft:${userId}:`,
    `codecoach.appnotes.v1.${userId}.`,
    "codecoach.round.",
    "codecoach.interview-message.",
    "codecoach.retry.",
  ];
  return keys().filter((k) => prefixes.some((p) => k.startsWith(p)));
}

/** How many unsent items this account has on this device (empty values don't count). */
export function countLocalWork(userId: string): number {
  return localWorkKeys(userId).filter((k) => {
    try {
      return Boolean(window.localStorage.getItem(k)?.trim());
    } catch {
      return false;
    }
  }).length;
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
