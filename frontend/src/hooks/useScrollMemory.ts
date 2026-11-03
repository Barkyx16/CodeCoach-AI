import { useEffect, useRef } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

/**
 * Remembers how far a list was scrolled, per history entry, and puts it back when the user
 * returns with Back/Forward, even after a reload, once the list's data has arrived. (The router's
 * own ScrollRestoration runs before async data renders, so a freshly loaded page is too short.)
 */
export function useScrollMemory(ready: boolean) {
  const location = useLocation();
  const navigation = useNavigationType();
  const key = `scroll:${location.key}`;
  const restored = useRef<string | null>(null);

  useEffect(() => {
    const save = () => {
      try { sessionStorage.setItem(key, String(Math.round(window.scrollY))); } catch { /* storage blocked: no memory */ }
    };
    window.addEventListener("scroll", save, { passive: true });
    return () => window.removeEventListener("scroll", save);
  }, [key]);

  useEffect(() => {
    if (!ready || restored.current === key) return;
    restored.current = key;
    if (navigation !== "POP") return;
    let y = Number.NaN;
    try { y = Number(sessionStorage.getItem(key)); } catch { /* storage blocked */ }
    if (Number.isFinite(y) && y > 0) requestAnimationFrame(() => window.scrollTo(0, y));
  }, [ready, navigation, key]);
}
