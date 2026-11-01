import { useCallback, useEffect, useRef, useState } from "react";

import { storage } from "@/lib/storage";

export type SaveState = "saved" | "saving" | "unsaved";

const key = (scope: string, slug: string) => `codecoach.draft.v1.${scope}.${slug}`;

/**
 * Autosaves editor content to localStorage (debounced) per user and problem, so a refresh,
 * crash or closed tab never loses work. `scope` keeps different users' drafts apart on a
 * shared browser.
 */
export function useDraft(slug: string, starterCode: string, scope = "anon", delayMs = 600) {
  const storageKey = key(scope, slug);
  const [draft, setDraft] = useState(() => ({ key: storageKey, code: storage.get(storageKey) ?? starterCode }));
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const timer = useRef<number | undefined>(undefined);

  // Switching problem or user loads that draft. Adjusting state during render (instead of in
  // an effect) is React's recommended pattern: no extra render with stale content.
  if (draft.key !== storageKey) {
    setDraft({ key: storageKey, code: storage.get(storageKey) ?? starterCode });
    setSaveState("saved");
  }
  const code = draft.code;

  const setCode = useCallback((next: string) => {
    setDraft({ key: storageKey, code: next });
    setSaveState("unsaved");
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      setSaveState("saving");
      if (next === starterCode) storage.remove(storageKey);
      else storage.set(storageKey, next);
      setSaveState("saved");
    }, delayMs);
  }, [storageKey, starterCode, delayMs]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const reset = useCallback(() => {
    window.clearTimeout(timer.current);
    storage.remove(storageKey);
    setDraft({ key: storageKey, code: starterCode });
    setSaveState("saved");
  }, [storageKey, starterCode]);

  const isModified = code !== starterCode;
  return { code, setCode, saveState, reset, isModified };
}
