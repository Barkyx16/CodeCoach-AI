import { useCallback, useEffect, useRef, useState } from "react";

/**
 * A browser copy of an unfinished form (Volume 9, prompt 2; NAVIGATION.md "Unfinished forms").
 *
 * - Kept per account and form (`form-draft:<user>:<kind>:<target>`), deleted with the account's
 *   other local work at sign-out (auth/localWork.ts). Only the form's own fields, its base (what
 *   the server had when the copy was made), the time and a schema version. Never a credential.
 * - Bounded: at most MAX_CHARS, and copies older than MAX_AGE_DAYS are dropped when read.
 * - Written a moment after typing stops, not on every keypress; removed when the form matches
 *   the saved values again.
 * - Offered, never applied by itself: `offer` holds a copy that differs from what was loaded, and
 *   nothing is written over it until the learner restores or discards it.
 * - A copy another tab of this browser wrote since this page last wrote is never overwritten:
 *   `competing` says so, and this page's text stays on the page only.
 * - A malformed or older-format copy is ignored and removed.
 * - `kept` is false when the browser refused the write (private mode, full): the page says the
 *   copy wasn't kept instead of implying it was.
 */
export const FORM_DRAFT_VERSION = 1;
export const MAX_CHARS = 60_000;
export const MAX_AGE_DAYS = 14;
const WRITE_DELAY_MS = 400;

export interface FormDraft<T> {
  v: number;
  form: T;
  /** What the server had when this copy was made (a revision or updated_at), if anything. */
  base: string | number | null;
  at: string;
  tab: string;
}

/** A stored copy is usable only if it has exactly these text fields. */
export function isTextForm(value: unknown, fields: readonly string[]): boolean {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return fields.every((f) => typeof v[f] === "string") && Object.keys(v).every((k) => fields.includes(k));
}

export const formDraftKey = (userId: string, kind: string, target: string) => `form-draft:${userId}:${kind}:${target}`;

export function readFormDraft<T>(key: string, isForm: (value: unknown) => value is T, now = Date.now()): FormDraft<T> | null {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(key);
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const d = JSON.parse(raw) as Partial<FormDraft<unknown>>;
    const at = typeof d.at === "string" ? Date.parse(d.at) : NaN;
    if (d.v === FORM_DRAFT_VERSION && isForm(d.form) && !Number.isNaN(at) && now - at <= MAX_AGE_DAYS * 86_400_000) {
      return d as FormDraft<T>;
    }
  } catch {
    /* malformed: dropped below */
  }
  clearFormDraft(key); // unreadable, another format, or too old: it can't be offered
  return null;
}

export function clearFormDraft(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* nothing kept */
  }
}

export function useFormDraft<T>({ storageKey, form, baseline, base, isForm, enabled = true }: {
  storageKey: string;
  form: T;
  /** The values as the server has them (loaded or last accepted). */
  baseline: T;
  base: string | number | null;
  isForm: (value: unknown) => value is T;
  enabled?: boolean;
}) {
  const [tabId] = useState(() => Math.random().toString(36).slice(2));
  const tab = useRef(tabId);
  const [initial] = useState(() => (enabled ? readFormDraft(storageKey, isForm) : null));
  // The newest copy this page has seen or written: anything written after it came from another tab.
  const lastWrite = useRef<string | null>(initial?.at ?? null);
  const [offer, setOffer] = useState<FormDraft<T> | null>(() =>
    initial && JSON.stringify(initial.form) !== JSON.stringify(baseline) ? initial : null);
  const [kept, setKept] = useState(true);
  const [competing, setCompeting] = useState(false);
  const changed = JSON.stringify(form) !== JSON.stringify(baseline);

  useEffect(() => {
    if (!enabled || offer) return; // an undecided copy is never written over
    const timer = window.setTimeout(() => {
      const existing = readFormDraft(storageKey, isForm);
      if (existing && existing.tab !== tab.current && (!lastWrite.current || existing.at > lastWrite.current)) {
        setCompeting(true); // another tab's newer copy stays; this text is on this page only
        return;
      }
      if (!changed) {
        if (existing) clearFormDraft(storageKey); // matches the saved values again: nothing to keep
        setKept(true);
        return;
      }
      const at = new Date().toISOString();
      const text = JSON.stringify({ v: FORM_DRAFT_VERSION, form, base, at, tab: tab.current } satisfies FormDraft<T>);
      if (text.length > MAX_CHARS) {
        setKept(false);
        return;
      }
      try {
        window.localStorage.setItem(storageKey, text);
        lastWrite.current = at;
        setKept(true);
      } catch {
        setKept(false);
      }
    }, WRITE_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [enabled, offer, storageKey, form, base, changed, isForm]);

  /** The copy, to put in the form; the caller compares `base` with what the server has now. */
  const restore = useCallback((): FormDraft<T> | null => {
    const d = offer;
    setOffer(null);
    return d;
  }, [offer]);
  const discard = useCallback(() => {
    clearFormDraft(storageKey); // only this form's copy
    setOffer(null);
  }, [storageKey]);
  /** After a confirmed save of `sent`: the copy goes only if nothing was typed since. */
  const accepted = useCallback((sent: T, now: T) => {
    if (JSON.stringify(sent) === JSON.stringify(now)) clearFormDraft(storageKey);
  }, [storageKey]);

  return { offer, restore, discard, accepted, kept: kept || !changed, competing };
}
