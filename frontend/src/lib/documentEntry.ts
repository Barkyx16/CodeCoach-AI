/**
 * The first location this document showed, and whether the learner has moved since (Volume 9,
 * prompt 6). React Router gives a document's first history entry the same key ("default") on every
 * fresh load, so remembered list positions can't tell a page opened directly from a return to it.
 * The first location of a document opened by a link, a bookmark or a typed address is a new
 * context and starts at the top; a reload or a browser Back/Forward into this document restores.
 */
let entry: string | null = null;
let left = false;

/** Called for every location shown (Layout, and the list hooks before they decide). */
export function noteLocation(key: string): void {
  if (entry === null) entry = key;
  else if (key !== entry) left = true;
}

function loadType(): string {
  try {
    return (performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined)?.type ?? "navigate";
  } catch {
    return "navigate";
  }
}

/** This is the document's first location, not returned to, and the document was freshly opened. */
export function isFreshVisit(key: string): boolean {
  return !left && key === entry && loadType() === "navigate";
}
