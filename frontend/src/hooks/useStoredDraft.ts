import { useCallback, useState } from "react";

import { dropCopy, readCopy, useCopySince, writeCopy } from "@/lib/deviceCopies";

function read(key: string): string {
  return readCopy(key) ?? "";
}

export function readStoredDraft(key: string): string {
  return read(key);
}

export function clearStoredDraft(key: string): void {
  dropCopy(key);
}

/**
 * Text that survives a reload, a failed request or a closed tab, kept in this browser under
 * `key`. Switching `key` (e.g. to the next question) loads that key's draft. The third value
 * says whether the last change was really kept on this device (false when storage is blocked
 * or full, or the copy was removed from "Your data" after this page opened it), so the page can
 * say so instead of implying it's safe.
 */
export function useStoredDraft(key: string): [string, (value: string) => void, boolean] {
  const [state, setState] = useState(() => ({ key, value: read(key), kept: true }));
  const current = state.key === key ? state : { key, value: read(key), kept: true };
  if (current !== state) setState(current);
  // A copy removed from "Your data" after this page opened it isn't written back (lib/deviceCopies).
  const since = useCopySince(key);
  const update = useCallback(
    (value: string) => {
      let kept = true;
      // Private mode, full, or removed on purpose: the draft lives for this page only.
      if (value) kept = writeCopy(key, value, since);
      else dropCopy(key);
      setState({ key, value, kept });
    },
    [key, since],
  );
  return [current.value, update, current.kept];
}
