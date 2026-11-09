import { useEffect, useLayoutEffect, useRef } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

import { announce } from "@/lib/announce";
import { isFreshVisit, noteLocation } from "@/lib/documentEntry";

/** The item a list entry was left from: its link, its neighbours' links, and where it sat. */
type Opened = { href: string; next: string | null; prev: string | null; top: number | null };

export const ITEM_GONE = "The item you opened isn't in this list any more.";

const rowHref = (row: Element | null | undefined) => row?.querySelector("a[href]")?.getAttribute("href") ?? null;

/** A list link that's shown (a hidden row is never focused). */
function shownLink(href: string | null): HTMLAnchorElement | null {
  if (!href) return null;
  return [...document.querySelectorAll<HTMLAnchorElement>("#main a[href]")]
    .find((a) => a.getAttribute("href") === href && a.getClientRects().length > 0) ?? null;
}

function readOpened(raw: string | null): Opened | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as Partial<Opened>;
    if (v && typeof v.href === "string") return { href: v.href, next: v.next ?? null, prev: v.prev ?? null, top: typeof v.top === "number" ? v.top : null };
  } catch { /* an older entry: just the link */ }
  return { href: raw, next: null, prev: null, top: null };
}

/**
 * Remembers where a list was, per history entry, and puts it back when the learner returns with
 * Back/Forward (or a breadcrumb that goes back), even after a reload, once the list's data has
 * arrived (Volume 7, prompt 7; Volume 9, prompt 6; NAVIGATION.md "Coming back to a list that
 * changed"). The router's own ScrollRestoration runs before async data renders.
 *
 * It restores by the item, not by pixels: the link that was opened is found again and put where
 * it was on screen, so records added above it or a new order don't land the learner on another
 * item. If it's gone (deleted, filtered out, moved to another page), the nearest neighbour that's
 * still there gets focus and a screen reader hears that the item isn't in the list any more; with
 * no neighbour either, focus goes to the page's main region at the remembered position. Only once
 * per return, and not at all if the learner scrolled, pressed a key or clicked while the list was
 * loading: they've taken over. A new entry (a link, a filter change, a direct visit) starts at the
 * top. Memory is per tab and per entry, and it's cleared when an account signs out here.
 *
 * The position is saved on scroll and, exactly, at the moment the entry is left. The listener is
 * removed in a layout effect, before the next page scrolls itself to the top, so that scroll can't
 * overwrite this entry's position with 0. While a Back/Forward visit is waiting to restore, scroll
 * events come from a page that's too short, so they aren't saved either.
 */
/**
 * `ready`: the list shows fresh data. Pass false while it's refetching: a cached list shown first
 * may still hold an item that the fresh one doesn't (restoring to it would focus a row that's
 * about to vanish).
 */
export function useScrollMemory(ready: boolean) {
  const location = useLocation();
  const navigation = useNavigationType();
  const key = `scroll:${location.key}`;
  const restored = useRef<string | null>(null);
  const waiting = useRef(false);
  const tookOver = useRef(false);

  useLayoutEffect(() => {
    noteLocation(location.key);
    // A return (Back/Forward, a reload) restores; the first page of a freshly opened document is
    // a new context, though the router calls its first render a POP too.
    waiting.current = navigation === "POP" && restored.current !== key && !isFreshVisit(location.key);
    tookOver.current = false;
  }, [navigation, key, location.key]);

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

  // While waiting to restore, the learner moving the page themselves means: leave it alone.
  useLayoutEffect(() => {
    const NAV_KEYS = new Set(["PageDown", "PageUp", "ArrowDown", "ArrowUp", "Home", "End", " ", "Tab"]);
    const take = () => { if (waiting.current) tookOver.current = true; };
    const onKey = (e: KeyboardEvent) => { if (NAV_KEYS.has(e.key)) take(); };
    window.addEventListener("wheel", take, { passive: true });
    window.addEventListener("touchmove", take, { passive: true });
    window.addEventListener("pointerdown", take);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("wheel", take);
      window.removeEventListener("touchmove", take);
      window.removeEventListener("pointerdown", take);
      window.removeEventListener("keydown", onKey);
    };
  }, [key]);

  // Which item was opened from this entry (the link activated, by click or keyboard), with its
  // neighbours and where it sat on screen, so coming back can find it, or the nearest one left.
  useLayoutEffect(() => {
    const remember = (event: Event) => {
      const link = (event.target as Element | null)?.closest?.("a[href]");
      if (!link || !document.getElementById("main")?.contains(link)) return;
      const row = link.closest("li");
      const opened: Opened = {
        href: link.getAttribute("href") ?? "",
        next: rowHref(row?.nextElementSibling), prev: rowHref(row?.previousElementSibling),
        top: Math.round(link.getBoundingClientRect().top),
      };
      try { sessionStorage.setItem(`focus:${key}`, JSON.stringify(opened)); } catch { /* storage blocked */ }
    };
    document.addEventListener("click", remember, true);
    return () => document.removeEventListener("click", remember, true);
  }, [key]);

  useEffect(() => {
    if (!ready || restored.current === key) return;
    restored.current = key;
    const restore = waiting.current && !tookOver.current; // a return not yet put back, and not taken over
    waiting.current = false;
    if (!restore) return;
    let y = Number.NaN;
    let opened: Opened | null = null;
    try {
      y = Number(sessionStorage.getItem(key));
      opened = readOpened(sessionStorage.getItem(`focus:${key}`));
    } catch { /* storage blocked */ }
    requestAnimationFrame(() => {
      if (tookOver.current) return;
      const putBack = (el: HTMLElement) => {
        if (opened?.top != null) window.scrollTo(0, window.scrollY + el.getBoundingClientRect().top - opened.top);
        else if (Number.isFinite(y) && y > 0) window.scrollTo(0, y);
        el.focus({ preventScroll: true });
      };
      const item = shownLink(opened?.href ?? null);
      if (item) return putBack(item);
      if (Number.isFinite(y) && y > 0) window.scrollTo(0, y); // the browser keeps it within the page
      if (!opened) return; // nothing was opened from here: the position is all there is
      const near = shownLink(opened.next) ?? shownLink(opened.prev);
      if (near) putBack(near);
      else document.getElementById("main")?.focus({ preventScroll: true });
      announce(ITEM_GONE);
    });
  }, [ready, navigation, key]);
}
