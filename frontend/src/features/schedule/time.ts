import type { ScheduleEntry } from "@/api/types";
import { todayIn } from "@/features/applications/dates";

/** Calendar arithmetic on plain YYYY-MM-DD dates (no time zone can shift them). */
export function addDays(day: string, n: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** The Monday on or before a date. */
export function startOfWeek(day: string): string {
  const dow = new Date(`${day}T00:00:00Z`).getUTCDay(); // 0 Sunday
  return addDays(day, -((dow + 6) % 7));
}

/** Which day an entry falls on where the learner's schedule is: all-day entries keep their date;
 * a timed entry is placed by its exact moment in the schedule's time zone. */
export function entryDay(e: Pick<ScheduleEntry, "all_day" | "on_date" | "starts_at">, tz: string): string {
  return e.all_day || !e.starts_at ? e.on_date : todayIn(tz, new Date(e.starts_at));
}

/** "18:30", plus the time as it was chosen when that was in another zone. */
export function timeLabel(e: Pick<ScheduleEntry, "starts_at" | "local_time" | "timezone">, tz: string): string {
  if (!e.starts_at) return "";
  const shown = new Intl.DateTimeFormat("en-GB", { timeZone: tz, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(e.starts_at));
  return e.timezone && e.timezone !== tz && e.local_time ? `${shown} (${e.local_time} ${zoneLabel(e.timezone)})` : shown;
}

export const zoneLabel = (z: string) => z.replace(/_/g, " ");

export const TIME_ZONES: string[] = (() => {
  try {
    return (Intl as unknown as { supportedValuesOf(k: string): string[] }).supportedValuesOf("timeZone");
  } catch {
    return ["UTC"];
  }
})();
