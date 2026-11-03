/**
 * Private work kept on this device, per account: unsent answers, code drafts, interview-round
 * drafts and note recovery copies. Signing out deletes the signed-out account's copies (after a
 * warning when there are any), so the next person on a shared device can't read them. Device
 * preferences (display, editor, voice) and public "Saved for offline" copies are kept: they
 * aren't account data. See docs/OFFLINE.md.
 */

function keys(): string[] {
  try {
    return Array.from({ length: window.localStorage.length }, (_, i) => window.localStorage.key(i) ?? "");
  } catch {
    return [];
  }
}

/** Keys that hold this account's private work. Round drafts are keyed by interview, which only
 * its owner can open; they're cleared with whoever signs out on this device. */
export function localWorkKeys(userId: string): string[] {
  const prefixes = [
    `codecoach.answer.${userId}.`,
    `codecoach.draft.v1.${userId}.`,
    `note-draft:${userId}:`,
    `note-capture:${userId}:`,
    `learn-draft:${userId}:`,
    `story-draft:${userId}:`,
    "codecoach.round.",
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
  for (const k of localWorkKeys(userId)) {
    try {
      window.localStorage.removeItem(k);
    } catch {
      /* storage blocked: nothing was kept */
    }
  }
}
