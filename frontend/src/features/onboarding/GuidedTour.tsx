import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { useCapabilities, useOnboarding, useUpdateOnboarding } from "@/api/queries";
import type { TourKind } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";

import { TOUR_STEPS } from "./tourSteps";

const ACTIVE = "data-tour-active";

/** Scroll so the element sits between the sticky header and the docked panel. */
function reveal(el: HTMLElement, panel: HTMLElement | null) {
  const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || document.documentElement.dataset.motion === "reduce";
  el.scrollIntoView?.({ block: "nearest" }); // scroll any inner container (the coding workspace's panels)
  const rect = el.getBoundingClientRect();
  const top = (document.querySelector(".header")?.getBoundingClientRect().bottom ?? 0) + 12;
  const bottom = (panel ? panel.getBoundingClientRect().top : window.innerHeight) - 12;
  if (rect.top >= top && rect.bottom <= bottom) return;
  const room = bottom - top;
  // Centre it in the free space when it fits; otherwise show its top.
  const delta = rect.height <= room ? rect.top - (top + (room - rect.height) / 2) : rect.top - top;
  window.scrollBy?.({ top: delta, behavior: reduce ? "auto" : "smooth" });
}

function findTarget(name: string): HTMLElement | null {
  const el = document.querySelector<HTMLElement>(`[data-tour="${name}"]`);
  // Hidden elements (another tab, focus mode, display: none) count as missing.
  return el && el.getClientRects().length > 0 ? el : null;
}

/**
 * The guided introduction for one kind of page. It runs only while the learner's tour is in
 * progress for this kind, explains real elements on the page (highlighted, never covered), and
 * can be left at any step. It's docked to the bottom of the screen and the page makes room for
 * it, so no control ends up behind it. It never touches the learner's answer or progress.
 */
export function GuidedTour({ kind }: { kind: TourKind }) {
  const { isAuthenticated } = useAuth();
  const state = useOnboarding(isAuthenticated);
  const active = state.data?.tour_status === "in_progress" && state.data.tour_kind === kind;
  if (!active || !state.data) return null;
  return <TourPanel kind={kind} step={Math.min(state.data.tour_step, TOUR_STEPS[kind].length - 1)} />;
}

function TourPanel({ kind, step }: { kind: TourKind; step: number }) {
  const { isAuthenticated } = useAuth();
  const update = useUpdateOnboarding();
  const execution = useCapabilities().data?.execution;
  const steps = TOUR_STEPS[kind];
  const current = steps[step]!;
  const last = step === steps.length - 1;
  const panelRef = useRef<HTMLElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  // Where focus was before the tour took it, to give it back when the tour ends.
  const returnFocus = useRef<Element | null>(null);
  const [target, setTarget] = useState<HTMLElement | null>(() => findTarget(current.target));

  useLayoutEffect(() => {
    if (!returnFocus.current && document.activeElement && document.activeElement !== document.body) {
      returnFocus.current = document.activeElement;
    }
  }, []);

  // Follow the target: it may appear later (feedback arrives), move, or vanish (tab change).
  useEffect(() => {
    const check = () => setTarget((prev) => {
      const next = findTarget(current.target);
      return next === prev ? prev : next;
    });
    check();
    const id = window.setInterval(check, 500);
    return () => window.clearInterval(id);
  }, [current.target]);

  useEffect(() => {
    if (!target) return;
    target.setAttribute(ACTIVE, "");
    reveal(target, panelRef.current);
    return () => target.removeAttribute(ACTIVE);
  }, [target]);

  // Each step's heading takes focus so a screen reader reads the new step.
  useEffect(() => {
    headingRef.current?.focus();
  }, [step]);

  // Make room at the bottom of the page for the panel (pages and the coding workspace use it).
  useLayoutEffect(() => {
    const panel = panelRef.current;
    const root = document.documentElement;
    if (!panel) return;
    const apply = () => root.style.setProperty("--tour-space", `${Math.ceil(panel.getBoundingClientRect().height)}px`);
    apply();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(apply) : null;
    observer?.observe(panel);
    return () => {
      observer?.disconnect();
      root.style.removeProperty("--tour-space");
    };
  }, []);

  function restoreFocus() {
    const el = returnFocus.current as HTMLElement | null;
    window.setTimeout(() => {
      // Back to where the learner was, else to the start of the page's main content.
      if (el && el.isConnected) el.focus();
      else document.getElementById("main")?.focus();
    }, 0);
  }

  function go(to: number) {
    update.mutate({ tour: "step", tour_step: to });
  }
  function end(action: "pause" | "complete") {
    update.mutate({ tour: action });
    restoreFocus();
  }

  const body = typeof current.body === "function" ? current.body({ execution, signedIn: isAuthenticated }) : current.body;
  return (
    <section ref={panelRef} className="tour" aria-label="Introduction"
      onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); end("pause"); } }}>
      <div className="tour__inner">
        <p className="tour__eyebrow">Introduction · step {step + 1} of {steps.length}</p>
        <h2 className="tour__title" id="tour-title" tabIndex={-1} ref={headingRef}>{current.title}</h2>
        <div id="tour-body" className="tour__body">
          <p>{body}</p>
          {!target && <p className="tour__note">{current.missing}</p>}
        </div>
        <div className="tour__actions">
          <Button size="sm" variant="ghost" onClick={() => end("pause")}>Leave the introduction</Button>
          <span className="tour__nav">
            <Button size="sm" variant="secondary" disabled={step === 0} onClick={() => go(step - 1)}>Back</Button>
            {last
              ? <Button size="sm" variant="primary" onClick={() => end("complete")}>Finish</Button>
              : <Button size="sm" variant="primary" onClick={() => go(step + 1)}>Next</Button>}
          </span>
        </div>
        {update.isError && <p className="tour__note" role="status">Couldn't save your place in the introduction. It still works on this page.</p>}
      </div>
    </section>
  );
}
