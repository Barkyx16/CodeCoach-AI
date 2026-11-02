import { useCallback, useState } from "react";

function read(key: string): string {
  try {
    return window.localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

export function readStoredDraft(key: string): string {
  return read(key);
}

export function clearStoredDraft(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* nothing to clear */
  }
}

/**
 * Text that survives a reload, a failed request or a closed tab, kept in this browser under
 * `key`. Switching `key` (e.g. to the next question) loads that key's draft.
 */
export function useStoredDraft(key: string): [string, (value: string) => void] {
  const [state, setState] = useState(() => ({ key, value: read(key) }));
  const current = state.key === key ? state : { key, value: read(key) };
  if (current !== state) setState(current);
  const update = useCallback(
    (value: string) => {
      setState({ key, value });
      try {
        if (value) window.localStorage.setItem(key, value);
        else window.localStorage.removeItem(key);
      } catch {
        /* private mode: the draft lives for this page only */
      }
    },
    [key],
  );
  return [current.value, update];
}
