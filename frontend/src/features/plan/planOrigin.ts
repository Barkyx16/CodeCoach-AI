/**
 * Which plan activity the learner opened, so the page it leads to can say "this is from your plan"
 * and bring them back to the next step afterwards. Kept in sessionStorage (this tab only) with no
 * learner text: the account id, the activity's id and title, where it opened and where it came
 * from. It belongs to one account and expires after 12 hours.
 */
export interface PlanOrigin {
  userId: string;
  itemId: string;
  title: string;
  /** The path the activity opened (a question, lesson, problem or interview page). */
  target: string;
  /** Where the learner started it: the dashboard or the plan page. */
  from: string;
  at: number;
}

const KEY = "codecoach.plan.origin.v1";
const MAX_AGE_MS = 12 * 60 * 60 * 1000;

export function rememberPlanOrigin(origin: Omit<PlanOrigin, "at">): void {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify({ ...origin, target: pathOf(origin.target), at: Date.now() }));
  } catch {
    /* without storage the page simply doesn't offer the way back */
  }
}

export function forgetPlanOrigin(): void {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    /* nothing to forget */
  }
}

/** The origin for this account and page, if the learner arrived here from their plan. */
export function planOriginFor(userId: string | undefined, pathname: string): PlanOrigin | null {
  if (!userId) return null;
  try {
    const raw = window.sessionStorage.getItem(KEY);
    if (!raw) return null;
    const o = JSON.parse(raw) as Partial<PlanOrigin>;
    const valid = typeof o.userId === "string" && typeof o.itemId === "string" && typeof o.title === "string"
      && typeof o.target === "string" && typeof o.from === "string" && typeof o.at === "number";
    if (!valid || o.userId !== userId || Date.now() - o.at! > MAX_AGE_MS) return null;
    return pathOf(pathname) === o.target ? (o as PlanOrigin) : null;
  } catch {
    return null;
  }
}

/** A path without its query or hash: a review link's ?answer= doesn't make it another page. */
function pathOf(href: string): string {
  return href.split(/[?#]/)[0]!;
}
