import { type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";

import { useCareers } from "@/api/queries";
import type { Career } from "@/api/types";

import { matchCareers } from "./careerSearch";

/**
 * Pick the job you're preparing for: a search box rather than a 110-item list. Type part of a
 * job's name (or its industry) and choose from the matches; with nothing typed, the list shows
 * every job by industry. The ARIA combobox pattern: arrow keys move through the matches, Enter
 * chooses, Escape closes and keeps the job that was chosen, and the number of matches is
 * announced. Typing alone never changes the job: only choosing one does.
 */
export function CareerSelect({ value, onChange, label = "Job you're preparing for", placeholder, hint, error, required }: {
  value: string;
  onChange(slug: string): void;
  label?: string;
  placeholder?: string;
  hint?: string;
  error?: string;
  required?: boolean;
}) {
  const id = useId();
  const listId = `${id}-list`;
  const optionId = (slug: string) => `${id}-option-${slug}`;
  const careers = useCareers();
  const all = useMemo(() => careers.data ?? [], [careers.data]);
  const selected = all.find((c) => c.slug === value);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState<string | null>(null); // null: show the chosen job's title
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  const typed = (query ?? "").trim();
  const matches = useMemo(() => matchCareers(all, typed), [all, typed]);
  // With nothing typed, the matches are every job, shown under its industry.
  const groups = useMemo(() => {
    if (typed) return null;
    const byCategory = new Map<string, Career[]>();
    for (const c of all) byCategory.set(c.category, [...(byCategory.get(c.category) ?? []), c]);
    return [...byCategory.entries()];
  }, [all, typed]);
  const options = useMemo(() => (groups ? groups.flatMap(([, list]) => list) : matches), [groups, matches]);
  const activeCareer = open ? options[active] : undefined;
  const activeId = activeCareer ? optionId(activeCareer.slug) : undefined;

  useEffect(() => {
    if (activeId) document.getElementById(activeId)?.scrollIntoView?.({ block: "nearest" });
  }, [activeId]);

  function openList() {
    if (!all.length) return;
    setOpen(true);
    const current = options.findIndex((c) => c.slug === value);
    setActive(query === null && current >= 0 ? current : 0);
  }
  function close() {
    setOpen(false);
    setQuery(null);
  }
  function choose(career: Career) {
    close();
    if (career.slug !== value) onChange(career.slug);
  }
  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) return openList();
      const step = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => Math.min(Math.max(i + step, 0), Math.max(options.length - 1, 0)));
    } else if (e.key === "Enter" && open) {
      e.preventDefault(); // choosing a job doesn't submit the form around it
      if (activeCareer) choose(activeCareer);
    } else if (e.key === "Escape" && (open || query !== null)) {
      e.preventDefault();
      close();
    }
  }

  const describedBy = [hint ? `${id}-hint` : "", error ? `${id}-error` : ""].filter(Boolean).join(" ") || undefined;
  const loading = !careers.data;
  const renderOption = (c: Career, showCategory: boolean) => (
    <li key={c.slug} id={optionId(c.slug)} role="option" data-value={c.slug}
      aria-selected={c.slug === value}
      className={`career-combo__option${activeCareer?.slug === c.slug ? " is-active" : ""}`}
      onMouseMove={() => setActive(options.indexOf(c))}
      onClick={() => choose(c)}>
      <span className="career-combo__title">{c.title}</span>
      {showCategory && <span className="career-combo__category">{c.category}</span>}
      {c.slug === value && <span className="career-combo__check" aria-hidden="true">✓</span>}
    </li>
  );

  return (
    <div className="field career-select">
      <label className="field__label" htmlFor={id}>{label}</label>
      <div className={`career-combo${open ? " is-open" : ""}`}>
        <svg className="career-combo__icon" aria-hidden="true" viewBox="0 0 20 20" width="18" height="18">
          <circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
          <path d="m13 13 4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
        <input ref={input} id={id} className="input career-combo__input" type="text" role="combobox"
          autoComplete="off" spellCheck={false} disabled={loading}
          aria-autocomplete="list" aria-expanded={open} aria-controls={listId}
          aria-activedescendant={activeId}
          aria-required={required || undefined} aria-invalid={error ? true : undefined} aria-describedby={describedBy}
          placeholder={loading ? (careers.isError ? "Couldn't load jobs" : "Loading jobs…") : (selected ? undefined : placeholder ?? "Search jobs, e.g. nurse")}
          value={query ?? selected?.title ?? ""}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); setActive(0); }}
          onClick={() => { if (!open) { openList(); input.current?.select(); } }}
          onKeyDown={onKeyDown}
          onBlur={close} />
        {/* mousedown would blur the input (and close the list) before a click could choose */}
        <ul id={listId} role="listbox" aria-label="Jobs" className="career-combo__list" hidden={!open}
          onMouseDown={(e) => e.preventDefault()}>
          {open && groups && groups.map(([category, list]) => (
            <li key={category} role="presentation">
              <div className="career-combo__group" id={`${id}-group-${category}`} aria-hidden="true">{category}</div>
              <ul role="group" aria-labelledby={`${id}-group-${category}`} className="career-combo__sublist">
                {list.map((c) => renderOption(c, false))}
              </ul>
            </li>
          ))}
          {open && !groups && matches.map((c) => renderOption(c, true))}
          {open && !groups && !matches.length && (
            <li role="presentation" className="career-combo__empty">No job matches “{typed}”. Try a shorter word.</li>
          )}
        </ul>
      </div>
      <span className="visually-hidden" role="status">
        {open && typed ? `${matches.length} ${matches.length === 1 ? "job matches" : "jobs match"}` : ""}
      </span>
      {hint && <span className="field__hint" id={`${id}-hint`}>{hint}</span>}
      {error && <span className="field__error" id={`${id}-error`}>{error}</span>}
    </div>
  );
}
