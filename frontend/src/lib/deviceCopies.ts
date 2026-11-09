import { useState } from "react";

/**
 * Copies of unsent work kept in this browser (auth/localWork.ts lists them), and the ones the
 * learner removed on purpose from "Your data" (Volume 10, prompt 10; docs/YOUR_DATA.md).
 *
 * A page that had a copy open when it was removed, in this tab or another, must not put it back
 * by itself: an autosave timer, an effect re-running after a refetch, a flush when the tab is
 * hidden. So every page notes the removal count when it opened its copy (`useCopySince`) and writes
 * through `writeCopy`, which refuses once that copy was removed after that point. The page keeps
 * its text on screen and says it isn't kept on this device; opening the page again starts a new
 * copy. A counter, not a clock: removals in any tab of this browser are numbered in order, so there
 * is no "same millisecond" to get wrong.
 *
 * What's remembered about a removal: the storage key (which names the account and the item's id,
 * never its content), its number and the time; at most 200, those over a day old dropped when the
 * next removal is recorded, and all of them at sign-out (the counter itself only grows, so a page
 * can't mistake an old number for a new one).
 */
export const REMOVALS_KEY = "codecoach.removed.v2";
const KEEP_MS = 24 * 60 * 60 * 1000;
const MAX = 200;

interface Removals {
  seq: number;
  removed: Record<string, { seq: number; at: number }>;
}

function removals(now?: number): Removals {
  try {
    const value = JSON.parse(window.localStorage.getItem(REMOVALS_KEY) ?? "null") as Partial<Removals> | null;
    const seq = typeof value?.seq === "number" && value.seq >= 0 ? value.seq : 0;
    const removed: Removals["removed"] = {};
    for (const [k, r] of Object.entries(value?.removed ?? {})) {
      if (r && typeof r.seq === "number" && typeof r.at === "number" && (now === undefined || now - r.at < KEEP_MS)) removed[k] = r;
    }
    return { seq, removed };
  } catch {
    return { seq: 0, removed: {} };
  }
}

/** How many removals this browser has numbered so far: a page notes it when it opens its copy. */
export function removalMark(): number {
  return removals().seq;
}

/** Whether this copy was removed on purpose after a page noted `mark`. */
export function removedSince(key: string, mark: number): boolean {
  const r = removals().removed[key];
  return r !== undefined && r.seq > mark;
}

/** The stored text, or null (nothing kept, or storage blocked). Never throws. */
export function readCopy(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/**
 * Keep `value` under `key` for a page that opened its copy at removal mark `since`. False when the
 * browser refused (private mode, full) or the learner removed this copy after the page opened it.
 */
export function writeCopy(key: string, value: string, since: number): boolean {
  if (removedSince(key, since)) return false;
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

/** The page's own clean-up (sent, saved, discarded, back to the saved version). Never throws. */
export function dropCopy(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* nothing kept */
  }
}

/**
 * Remove these copies on purpose: the removal is recorded first, so a page still open with one of
 * them can't write it back, then each copy goes. `failed` are the keys still there (blocked
 * storage); `guarded` is false when the removal couldn't be recorded, so a page still open
 * elsewhere could keep its copy again. Nothing else in the browser is touched.
 */
export function removeCopies(keys: string[], now = Date.now()): { removed: string[]; failed: string[]; guarded: boolean } {
  const current = removals(now);
  const seq = current.seq + 1;
  const removedNow = { ...current.removed };
  for (const k of keys) removedNow[k] = { seq, at: now };
  const newest = Object.entries(removedNow).sort(([, a], [, b]) => b.seq - a.seq).slice(0, MAX);
  let guarded = true;
  try {
    window.localStorage.setItem(REMOVALS_KEY, JSON.stringify({ seq, removed: Object.fromEntries(newest) }));
  } catch {
    guarded = false;
  }
  const removed: string[] = [];
  const failed: string[] = [];
  for (const k of keys) {
    try {
      window.localStorage.removeItem(k);
      (window.localStorage.getItem(k) === null ? removed : failed).push(k);
    } catch {
      failed.push(k);
    }
  }
  return { removed, failed, guarded };
}

/** Sign-out: which copies were removed goes with the account's copies; the counter stays. */
export function forgetRemovals(): void {
  const { seq } = removals();
  if (seq === 0) return; // nothing was ever removed here: leave no trace
  try {
    window.localStorage.setItem(REMOVALS_KEY, JSON.stringify({ seq, removed: {} }));
  } catch {
    /* storage blocked: nothing was kept */
  }
}

/** The removal mark when this component opened the copy under `key`, noted again when `key` changes. */
export function useCopySince(key: string): number {
  const [opened, setOpened] = useState(() => ({ key, mark: removalMark() }));
  if (opened.key !== key) {
    const next = { key, mark: removalMark() };
    setOpened(next);
    return next.mark;
  }
  return opened.mark;
}
