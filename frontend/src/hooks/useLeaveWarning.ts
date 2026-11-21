import { useEffect, useId } from "react";

/** Work on this page that would be lost by leaving or reloading (e.g. storage failed), and, where
 * the page said, what it is ("the job description"), for the question the leave guard asks. */
const unsafe = new Map<string, string | undefined>();

export function hasUnretainedWork(): boolean {
  return unsafe.size > 0;
}

/** What the pages with unsaved work said they hold, for the leave question (may be empty). */
export function unretainedWorkLabels(): string[] {
  return [...new Set([...unsafe.values()].filter((v): v is string => Boolean(v)))];
}

/** The question the leave guard asks: what would be discarded, and which button does what. */
export function leaveQuestion(labels: string[] = unretainedWorkLabels()): string {
  const what = labels.length ? `Your changes to ${labels.join(" and ")} aren't saved` : "This page has changes that aren't saved yet";
  return `${what}, and leaving would discard them. Leave anyway? (Cancel stays here with everything as it is.)`;
}

/** Until when the next in-app navigation follows a save that just succeeded (ms since the epoch). */
let afterSaveUntil = 0;

/**
 * The page's work just reached the server and the page moves on (a new story opening at its own
 * address): let that navigation through without asking, even though this browser couldn't keep a
 * local copy. Good for one navigation, within a second.
 */
export function allowLeaveAfterSave(): void {
  afterSaveUntil = Date.now() + 1000;
}

/** For the leave guard: is this navigation the one a save just allowed? Consumed once. */
export function takeLeaveAfterSave(): boolean {
  const allowed = Date.now() < afterSaveUntil;
  afterSaveUntil = 0;
  return allowed;
}

/**
 * While `active`, the browser asks before the page is closed or reloaded, in-app navigation to
 * another page asks first (app/LeaveGuard.tsx), and an app update waits for confirmation. Use it
 * when leaving would lose work: edits held only in memory, or a draft this browser can't keep.
 */
export function useLeaveWarning(active: boolean, what?: string): void {
  const id = useId();
  useEffect(() => {
    if (!active) return;
    unsafe.set(id, what);
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = ""; // older browsers need it set
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      unsafe.delete(id);
      window.removeEventListener("beforeunload", warn);
    };
  }, [active, id, what]);
}
