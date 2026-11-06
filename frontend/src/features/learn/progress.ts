import { useEffect, useState } from "react";

import type { UnitProgress } from "@/api/types";

export function statusLabel(p: UnitProgress | undefined): { text: string; tone: string } {
  if (!p || !p.started) return { text: "Not started", tone: "neutral" };
  if (p.check_passed && p.practiced) return { text: "Check passed · practised", tone: "success" };
  if (p.check_passed) return { text: "Check passed", tone: "success" };
  if (p.read) return { text: "Read", tone: "info" };
  return { text: "Started", tone: "info" };
}

/** Which section is in view and how far through the unit the reader has got. */
export function useReadingProgress(ids: string[], ready: boolean): { current: number; furthest: number } {
  const [state, setState] = useState({ current: 0, furthest: 0 });
  const key = ids.join("|");
  useEffect(() => {
    if (!ready || typeof IntersectionObserver === "undefined") return;
    const els = ids.map((i) => document.getElementById(i)).filter((x): x is HTMLElement => Boolean(x));
    const visible = new Set<number>();
    const observer = new IntersectionObserver((entries) => {
      for (const e of entries) {
        const index = els.indexOf(e.target as HTMLElement);
        if (e.isIntersecting) visible.add(index);
        else visible.delete(index);
      }
      if (visible.size === 0) return;
      const current = Math.min(...visible);
      setState((s) => ({ current, furthest: Math.max(s.furthest, Math.max(...visible)) }));
    }, { rootMargin: "0px 0px -40% 0px" });
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [key, ready]); // eslint-disable-line react-hooks/exhaustive-deps
  return state;
}
