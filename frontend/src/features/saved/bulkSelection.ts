import { useCallback, useMemo, useState } from "react";

import type { BatchResult } from "@/api/types";

/** The selection and outcome rules behind the bulk actions (docs/BULK_ACTIONS.md); see bulk.tsx. */

export const BATCH_LIMIT = 50;

export function useSelection(keys: string[]) {
  const [picked, setPicked] = useState<Set<string>>(() => new Set());
  const shown = useMemo(() => new Set(keys), [keys]);
  // Only what's still on screen counts.
  const selected = useMemo(() => keys.filter((k) => picked.has(k)), [keys, picked]);
  const toggle = useCallback((key: string, on: boolean) => {
    setPicked((now) => {
      const next = new Set(now);
      if (on) next.add(key);
      else next.delete(key);
      return next;
    });
  }, []);
  const setAll = useCallback((on: boolean) => setPicked(on ? new Set(shown) : new Set()), [shown]);
  const keep = useCallback((only: string[]) => setPicked(new Set(only)), []);
  return { selected, isSelected: (k: string) => picked.has(k) && shown.has(k), toggle, setAll, keep, all: keys.length > 0 && selected.length === keys.length };
}

const OUTCOME: Record<BatchResult["outcome"], { label: string; done: boolean }> = {
  added: { label: "Added", done: true },
  already_there: { label: "Already there", done: true },
  removed: { label: "Removed", done: true },
  not_there: { label: "Wasn't there", done: true },
  repeated: { label: "Listed twice", done: true },
  unavailable: { label: "Not available", done: false },
  full: { label: "Didn't fit", done: false },
};

export const isDone = (r: BatchResult) => OUTCOME[r.outcome].done;

export const outcomeLabel = (r: BatchResult) => OUTCOME[r.outcome].label;
