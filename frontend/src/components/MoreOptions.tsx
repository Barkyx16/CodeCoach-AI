import { type ReactNode, useEffect, useId, useRef, useState } from "react";

/**
 * Secondary actions behind one labelled button, so a card keeps a single obvious action. A
 * disclosure: the button says whether it's open (aria-expanded), Tab moves through the actions,
 * Escape closes it and returns focus to the button, and choosing an action, clicking elsewhere or
 * tabbing away closes it.
 */
export function MoreOptions({ label = "More options", children }: { label?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);

  return (
    <div className="more-options" ref={root}
      onKeyDown={(e) => {
        if (e.key !== "Escape" || !open) return;
        e.stopPropagation();
        setOpen(false);
        button.current?.focus();
      }}
      onBlur={(e) => { if (open && !root.current?.contains(e.relatedTarget as Node | null)) setOpen(false); }}>
      <button ref={button} type="button" className="btn btn--ghost btn--md more-options__toggle"
        aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)}>
        {label}
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" className="more-options__chevron">
          <path d="m2.5 4.5 3.5 3.5 3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {/* A click on any action inside closes the panel after the action has run. */}
      <div id={id} className="more-options__panel" hidden={!open} onClick={() => setOpen(false)}>
        {children}
      </div>
    </div>
  );
}
