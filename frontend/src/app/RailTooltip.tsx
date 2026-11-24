import { useEffect, useRef, useState, type RefObject } from "react";

/** The rail is showing: icons-only chosen, a wide enough window, and not in focus mode. */
function railShowing(root: HTMLElement = document.documentElement): boolean {
  if (root.getAttribute("data-sidebar") !== "icons" || root.hasAttribute("data-focus")) return false;
  try {
    return window.matchMedia("(min-width: 1101px)").matches;
  } catch {
    return false;
  }
}

interface Tip { text: string; top: number; left: number }

/**
 * In the icon rail, the name of what's under the pointer or has keyboard focus, beside the rail.
 * Every control already has that name as its accessible name, so this is for the eyes only
 * (aria-hidden). It follows WCAG 1.4.13: it stays while the pointer moves onto it, Escape
 * dismisses it, and it goes when the pointer and focus have both left. Names come from each
 * control's data-tip attribute.
 */
export function RailTooltip({ container }: { container: RefObject<HTMLElement | null> }) {
  const [tip, setTip] = useState<Tip | null>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const hideTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    const host = container.current;
    if (!host) return;
    const owner = (node: EventTarget | null): HTMLElement | null =>
      node instanceof Element ? node.closest<HTMLElement>("[data-tip]") : null;
    const cancelHide = () => window.clearTimeout(hideTimer.current);
    const hideSoon = () => {
      cancelHide();
      // A moment's grace, so the pointer can cross onto the label itself.
      hideTimer.current = window.setTimeout(() => setTip(null), 150);
    };
    const show = (el: HTMLElement) => {
      cancelHide();
      if (!railShowing() || !host.contains(el)) {
        setTip(null);
        return;
      }
      const box = el.getBoundingClientRect();
      setTip({ text: el.dataset.tip ?? "", top: box.top + box.height / 2, left: host.getBoundingClientRect().right + 10 });
    };
    const onOver = (event: PointerEvent) => {
      const el = owner(event.target);
      if (el) show(el);
    };
    const onOut = (event: PointerEvent) => {
      const from = owner(event.target);
      const to = event.relatedTarget as Node | null;
      if (!from || (to && (from.contains(to) || tipRef.current?.contains(to)))) return;
      hideSoon();
    };
    const onFocusIn = (event: FocusEvent) => {
      const el = owner(event.target);
      if (el) show(el);
      else setTip(null);
    };
    const onFocusOut = (event: FocusEvent) => {
      if (!host.contains(event.relatedTarget as Node | null)) setTip(null);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setTip(null);
    };
    const onScroll = () => setTip(null);
    host.addEventListener("pointerover", onOver);
    host.addEventListener("pointerout", onOut);
    host.addEventListener("focusin", onFocusIn);
    host.addEventListener("focusout", onFocusOut);
    host.addEventListener("scroll", onScroll, true);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onScroll);
    return () => {
      cancelHide();
      host.removeEventListener("pointerover", onOver);
      host.removeEventListener("pointerout", onOut);
      host.removeEventListener("focusin", onFocusIn);
      host.removeEventListener("focusout", onFocusOut);
      host.removeEventListener("scroll", onScroll, true);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onScroll);
    };
  }, [container]);

  if (!tip) return null;
  return (
    <div ref={tipRef} className="rail-tip" aria-hidden="true" style={{ top: tip.top, left: tip.left }}
      onPointerEnter={() => window.clearTimeout(hideTimer.current)}
      onPointerLeave={() => setTip(null)}>
      {tip.text}
    </div>
  );
}
