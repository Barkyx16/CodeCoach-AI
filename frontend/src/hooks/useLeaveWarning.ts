import { useEffect, useId } from "react";

/** Work on this page that would be lost by leaving or reloading (e.g. storage failed). */
const unsafe = new Set<string>();

export function hasUnretainedWork(): boolean {
  return unsafe.size > 0;
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
export function useLeaveWarning(active: boolean): void {
  const id = useId();
  useEffect(() => {
    if (!active) return;
    unsafe.add(id);
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = ""; // older browsers need it set
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      unsafe.delete(id);
      window.removeEventListener("beforeunload", warn);
    };
  }, [active, id]);
}
