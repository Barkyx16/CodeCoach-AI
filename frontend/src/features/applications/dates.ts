import type { ApplicationEvent } from "@/api/types";

/**
 * Calendar dates in the learner's own time zone. A due date is a plain date ("2026-11-04"), so
 * "today" must be today where the learner is, not in UTC: at 23:30 UTC it's already tomorrow in
 * Tokyo and still today in Chicago.
 */

/** The browser's IANA time zone (e.g. "America/Chicago"), or UTC if it can't tell. */
export function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

/** Today's date (YYYY-MM-DD) in a time zone. */
export function todayIn(timeZone: string, now: Date = new Date()): string {
  // en-CA formats as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

/** Whole days from `today` to `date` (both YYYY-MM-DD), counted on the calendar. */
export function daysBetween(today: string, date: string): number {
  const a = Date.UTC(+today.slice(0, 4), +today.slice(5, 7) - 1, +today.slice(8, 10));
  const b = Date.UTC(+date.slice(0, 4), +date.slice(5, 7) - 1, +date.slice(8, 10));
  return Math.round((b - a) / 86_400_000);
}

/** Neutral wording: an overdue item is just "was due", never a warning about the learner. */
export function dueLabel(date: string, today: string): string {
  const d = daysBetween(today, date);
  if (d === 0) return "Due today";
  if (d === 1) return "Due tomorrow";
  if (d > 1) return `Due in ${d} days`;
  if (d === -1) return "Was due yesterday";
  return `Was due ${-d} days ago`;
}

/** Readable date for a YYYY-MM-DD, without shifting it through UTC. */
export function formatDay(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(Date.UTC(y!, m! - 1, d!)).toLocaleDateString(undefined, { timeZone: "UTC", weekday: "short", day: "numeric", month: "short", year: "numeric" });
}

/** How an event's time reads, with what's still unknown said plainly. */
export function describeWhen(e: Pick<ApplicationEvent, "on_date" | "local_time" | "timezone">): string {
  if (!e.on_date) return "Date not known yet";
  const day = formatDay(e.on_date);
  if (!e.local_time) return `${day} (time not known yet)`;
  return `${day}, ${e.local_time}${e.timezone ? ` ${e.timezone.replace(/_/g, " ")}` : ""}`;
}
