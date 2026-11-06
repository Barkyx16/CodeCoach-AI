import { useLocation } from "react-router-dom";

/** Where a page was opened from, when it was opened from a list that wants it back (e.g. History). */
export function useCameFrom(): { from: string; label: string } | null {
  const state = useLocation().state as { from?: string; fromLabel?: string } | null;
  return state?.from ? { from: state.from, label: state.fromLabel ?? "Back" } : null;
}
