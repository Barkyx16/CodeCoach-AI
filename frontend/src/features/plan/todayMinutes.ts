export const TODAY_OPTIONS = [5, 15, 30] as const;
const KEY = "codecoach.today.minutes";

/** The time budget the learner last chose for Today (15 minutes until they choose). */
export function savedMinutes(): number {
  try {
    const v = Number(window.localStorage.getItem(KEY));
    return (TODAY_OPTIONS as readonly number[]).includes(v) ? v : 15;
  } catch {
    return 15;
  }
}

export function saveMinutes(m: number): void {
  try {
    window.localStorage.setItem(KEY, String(m));
  } catch {
    /* not remembered */
  }
}
