import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

export type LinkedAttempt = "none" | "loading" | "shown" | "missing";

/**
 * Open the attempt a link names (`?attempt=<id>`, from a History row: Volume 17, prompt 2): loads it
 * once, hands it to the page to show, and brings the element `focusId` names into view. "missing"
 * when it can't be read (another account's, deleted, or gone), so the page can say so.
 */
export function useLinkedAttempt<T>(load: (id: string) => Promise<T>, show: (attempt: T) => void, focusId?: string): LinkedAttempt {
  const [params] = useSearchParams();
  const id = params.get("attempt");
  const [state, setState] = useState<{ id: string | null; status: LinkedAttempt }>({ id: null, status: "none" });
  const latest = useRef({ load, show, focusId });
  useEffect(() => { latest.current = { load, show, focusId }; });
  useEffect(() => {
    if (!id) return;
    let live = true;
    queueMicrotask(() => { if (live) setState({ id, status: "loading" }); });
    latest.current.load(id).then(
      (attempt) => {
        if (!live) return;
        latest.current.show(attempt);
        setState({ id, status: "shown" });
        const target = latest.current.focusId;
        if (target) requestAnimationFrame(() => {
          const el = document.getElementById(target);
          el?.scrollIntoView?.({ block: "start" });
          el?.focus?.({ preventScroll: true });
        });
      },
      () => { if (live) setState({ id, status: "missing" }); },
    );
    return () => { live = false; };
  }, [id]);
  return id && state.id === id ? state.status : id ? "loading" : "none";
}

export const LINKED_MISSING = "That attempt couldn't be opened: it may have been deleted, or it isn't one of yours.";
