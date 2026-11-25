import type { ScheduleEntry, ScheduleSettings } from "@/api/types";

/**
 * In-app reminders, worked out on this device while CodeCoach is open. Nothing is queued on a
 * server, so nothing can be "delivered" behind the learner's back: a reminder is only ever a
 * message on the screen they're looking at. Off unless turned on; quiet hours are respected.
 */

/** "HH:MM" now, in a time zone. */
export function clockIn(timeZone: string, now: Date): string {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(now);
  const h = parts.find((p) => p.type === "hour")?.value ?? "00";
  const m = parts.find((p) => p.type === "minute")?.value ?? "00";
  return `${h}:${m}`;
}

/** Quiet hours can cross midnight (22:00 to 07:00). Equal start and end means none. */
export function inQuietHours(now: Date, s: Pick<ScheduleSettings, "quiet_start" | "quiet_end">, timeZone: string): boolean {
  if (!s.quiet_start || !s.quiet_end || s.quiet_start === s.quiet_end) return false;
  const t = clockIn(timeZone, now);
  return s.quiet_start < s.quiet_end ? t >= s.quiet_start && t < s.quiet_end : t >= s.quiet_start || t < s.quiet_end;
}

export const reminderKey = (e: Pick<ScheduleEntry, "uid" | "sequence">) => `${e.uid}#${e.sequence}`;

/** Entries to remind about now: timed, still scheduled, not done, starting within the lead time. */
export function dueReminders(entries: ScheduleEntry[], now: Date, s: ScheduleSettings, timeZone: string, shown: ReadonlySet<string>): ScheduleEntry[] {
  if (!s.reminders || inQuietHours(now, s, timeZone)) return [];
  const lead = s.reminder_minutes * 60_000;
  return entries.filter((e) => {
    if (e.status !== "scheduled" || e.done_at || !e.starts_at || shown.has(reminderKey(e))) return false;
    const until = new Date(e.starts_at).getTime() - now.getTime();
    return until >= 0 && until <= lead;
  });
}
