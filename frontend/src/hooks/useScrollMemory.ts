import { useEffect, useLayoutEffect, useRef } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

/**
 * Remembers how far a list was scrolled, per history entry, and puts it back when the user
 * returns with Back/Forward, even after a reload, once the list's data has arrived. (The router's
 * own ScrollRestoration runs before async data renders, so a freshly loaded page is too short.)
 *
 * The position is saved on scroll and, exactly, at the moment the entry is left. The listener is
 * removed in a layout effect, before the next page scrolls itself to the top, so that scroll can't
 * overwrite this entry's position with 0 (it used to, depending on timing). While a Back/Forward
 * visit is still waiting to restore, scroll events come from a page that's too short, so they
 * aren't saved either.
 */
export function useScrollMemory(ready: boolean) {
  const location = useLocation();
  const navigation = useNavigationType();
  const key = `scroll:${location.key}`;
  const restored = useRef<string | null>(null);
  const waiting = useRef(false);

  useLayoutEffect(() => {
    waiting.current = navigation === "POP" && restored.current !== key;
  }, [navigation, key]);

  useLayoutEffect(() => {
    const store = (y: number) => {
      try { sessionStorage.setItem(key, String(Math.round(y))); } catch { /* storage blocked: no memory */ }
    };
    const save = () => { if (!waiting.current) store(window.scrollY); };
    window.addEventListener("scroll", save, { passive: true });
    return () => {
      window.removeEventListener("scroll", save);
      if (!waiting.current) store(window.scrollY); // where it was when this entry was left
    };
  }, [key]);

  useEffect(() => {
    if (!ready || restored.current === key) return;
    restored.current = key;
    const restore = waiting.current; // a Back/Forward visit (or a reload) that hasn't been put back yet
    waiting.current = false;
    if (!restore) return;
    let y = Number.NaN;
    try { y = Number(sessionStorage.getItem(key)); } catch { /* storage blocked */ }
    if (Number.isFinite(y) && y > 0) requestAnimationFrame(() => window.scrollTo(0, y));
  }, [ready, navigation, key]);
}
