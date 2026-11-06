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
 * `key`. Switching `key` (e.g. to the next question) loads that key's draft. The third value
 * says whether the last change was really kept on this device (false when storage is blocked
 * or full), so the page can say so instead of implying it's safe.
 */
export function useStoredDraft(key: string): [string, (value: string) => void, boolean] {
  const [state, setState] = useState(() => ({ key, value: read(key), kept: true }));
  const current = state.key === key ? state : { key, value: read(key), kept: true };
  if (current !== state) setState(current);
  const update = useCallback(
    (value: string) => {
      let kept = true;
      try {
        if (value) window.localStorage.setItem(key, value);
        else window.localStorage.removeItem(key);
      } catch {
        kept = !value; // private mode or full: the draft lives for this page only
      }
      setState({ key, value, kept });
    },
    [key],
  );
  return [current.value, update, current.kept];
}
