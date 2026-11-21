import { useLocation } from "react-router-dom";

/**
 * Router state for a link out of a list, so the page it opens shows "Back to …" and returns to
 * this exact list (its filters in the URL, and its scroll position if the list remembers it).
 */
export function useReturnHere(label: string): { from: string; fromLabel: string } {
  const { pathname, search } = useLocation();
  return { from: pathname + search, fromLabel: label };
}
