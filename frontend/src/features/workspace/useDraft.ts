import { useCallback, useEffect, useRef, useState } from "react";

import { useCopySince, writeCopy } from "@/lib/deviceCopies";
import { storage } from "@/lib/storage";

export type SaveState = "saved" | "saving" | "unsaved" | "error";

const key = (scope: string, slug: string) => `codecoach.draft.v1.${scope}.${slug}`;

/**
 * Autosaves editor content to localStorage (debounced) per user and problem, so a refresh,
 * crash or closed tab never loses work. `scope` keeps different users' drafts apart on a
 * shared browser.
 */
export function useDraft(slug: string, starterCode: string, scope = "anon", delayMs = 600) {
  const storageKey = key(scope, slug);
  const [draft, setDraft] = useState(() => ({
    key: storageKey,
    starter: starterCode,
    code: storage.get(storageKey) ?? starterCode,
  }));
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const timer = useRef<number | undefined>(undefined);
  // A copy removed from "Your data" after this editor opened it isn't written back (lib/deviceCopies).
  const since = useCopySince(storageKey);
  const pending = useRef<{ key: string; code: string; starter: string; since: number } | null>(null);
  const persist = useCallback(() => {
    const change = pending.current;
    if (!change) return true;
    const saved = change.code === change.starter
      ? storage.remove(change.key) : writeCopy(change.key, change.code, change.since);
    if (saved) pending.current = null;
    return saved;
  }, []);

  // Switching problem or user loads that draft. Adjusting state during render (instead of in
  // an effect) is React's recommended pattern: no extra render with stale content.
  if (draft.key !== storageKey) {
    setDraft({ key: storageKey, starter: starterCode, code: storage.get(storageKey) ?? starterCode });
    setSaveState("saved");
  } else if (draft.starter !== starterCode) {
    // The starter code arrived (or changed) after mount. Adopt it unless the user already typed.
    const untouched = draft.code === draft.starter;
    setDraft({ key: storageKey, starter: starterCode, code: untouched ? starterCode : draft.code });
  }
  const code = draft.code;

  const setCode = useCallback((next: string) => {
    setDraft({ key: storageKey, starter: starterCode, code: next });
    pending.current = { key: storageKey, starter: starterCode, code: next, since };
    setSaveState("unsaved");
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      setSaveState("saving");
      setSaveState(persist() ? "saved" : "error");
    }, delayMs);
  }, [storageKey, starterCode, delayMs, persist, since]);

  useEffect(() => {
    const flush = () => { window.clearTimeout(timer.current); persist(); };
    const onHide = () => {
      window.clearTimeout(timer.current);
      if (pending.current) setSaveState(persist() ? "saved" : "error");
    };
    const onVisibility = () => { if (document.visibilityState === "hidden") onHide(); };
    window.addEventListener("pagehide", onHide);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      flush(); // Navigation must save even before the debounce delay has elapsed.
      window.removeEventListener("pagehide", onHide);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [storageKey, persist]);

  const reset = useCallback(() => {
    window.clearTimeout(timer.current);
    pending.current = { key: storageKey, starter: starterCode, code: starterCode, since };
    setDraft({ key: storageKey, starter: starterCode, code: starterCode });
    setSaveState(persist() ? "saved" : "error");
  }, [storageKey, starterCode, persist, since]);

  const isModified = code !== starterCode;
  return { code, setCode, saveState, reset, isModified };
}
