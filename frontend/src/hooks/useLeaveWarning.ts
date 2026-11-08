import { useEffect, useId } from "react";

/** Work on this page that would be lost by leaving or reloading (e.g. storage failed). */
const unsafe = new Set<string>();

export function hasUnretainedWork(): boolean {
  return unsafe.size > 0;
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
