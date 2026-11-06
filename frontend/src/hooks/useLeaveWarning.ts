import { useEffect, useId } from "react";

/** Work on this page that would be lost by leaving or reloading (e.g. storage failed). */
const unsafe = new Set<string>();

export function hasUnretainedWork(): boolean {
  return unsafe.size > 0;
}

/**
 * While `active`, the browser asks before the page is closed or reloaded, and an app update
 * waits for confirmation. Use it only when the draft really can't be kept.
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
