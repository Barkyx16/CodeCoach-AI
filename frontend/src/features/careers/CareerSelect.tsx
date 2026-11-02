import { useId, useMemo } from "react";

import { useCareers } from "@/api/queries";
import type { Career } from "@/api/types";

/**
 * Pick the job you're preparing for. A native <select> grouped by industry: with 100+ jobs it's
 * fully keyboard and screen-reader friendly, and typing a letter jumps through the list.
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
  const careers = useCareers();
  const groups = useMemo(() => {
    const byCategory = new Map<string, Career[]>();
    for (const c of careers.data ?? []) byCategory.set(c.category, [...(byCategory.get(c.category) ?? []), c]);
    return [...byCategory.entries()];
  }, [careers.data]);
  const describedBy = [hint ? `${id}-hint` : "", error ? `${id}-error` : ""].filter(Boolean).join(" ") || undefined;
  return (
    <div className="field career-select">
      <label className="field__label" htmlFor={id}>{label}</label>
      <select id={id} className="select" value={careers.data ? value : ""} required={required}
        disabled={!careers.data} aria-invalid={error ? true : undefined} aria-describedby={describedBy}
        onChange={(e) => onChange(e.target.value)}>
        {!careers.data && <option value="">{careers.isError ? "Couldn't load jobs" : "Loading jobs…"}</option>}
        {careers.data && placeholder && <option value="" disabled>{placeholder}</option>}
        {groups.map(([category, list]) => (
          <optgroup key={category} label={category}>
            {list.map((c) => <option key={c.slug} value={c.slug}>{c.title}</option>)}
          </optgroup>
        ))}
      </select>
      {hint && <span className="field__hint" id={`${id}-hint`}>{hint}</span>}
      {error && <span className="field__error" id={`${id}-error`}>{error}</span>}
    </div>
  );
}
