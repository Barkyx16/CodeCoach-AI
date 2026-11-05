import type { ScheduleEntry, ScheduleSettings } from "@/api/types";

import { dueReminders, inQuietHours, reminderKey } from "./dueReminders";
import { addDays, entryDay, startOfWeek, timeLabel } from "./time";

const entry = (over: Partial<ScheduleEntry>): ScheduleEntry => ({
  id: "e", uid: "u@codecoach", kind: "question", ref: "r", title: "T", href: null, all_day: false, on_date: "2026-11-10",
  local_time: "18:30", timezone: "America/Chicago", starts_at: "2026-11-11T00:30:00Z", ends_at: null, duration_min: 30,
  status: "scheduled", done_at: null, available: true, conflicts: [], sequence: 0, notes: "", created_at: "2026-11-01T00:00:00Z", ...over,
});
const settings = (over: Partial<ScheduleSettings> = {}): ScheduleSettings => ({ timezone: "America/Chicago", reminders: true, reminder_minutes: 10, quiet_start: null, quiet_end: null, ...over });

describe("calendar dates", () => {
  it("adds days across month, year and daylight-saving changes without shifting", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDays("2026-03-07", 2)).toBe("2026-03-09");
    expect(startOfWeek("2026-11-08")).toBe("2026-11-02"); // a Sunday belongs to the week starting Monday
    expect(startOfWeek("2026-11-02")).toBe("2026-11-02");
  });

  it("places a timed entry on the day it falls where the schedule is, and keeps all-day dates", () => {
    const e = entry({});
    expect(entryDay(e, "America/Chicago")).toBe("2026-11-10"); // 18:30 Chicago
    expect(entryDay(e, "Asia/Tokyo")).toBe("2026-11-11"); // 09:30 the next morning in Tokyo
    expect(entryDay(entry({ all_day: true, starts_at: null }), "Asia/Tokyo")).toBe("2026-11-10");
    expect(timeLabel(e, "America/Chicago")).toBe("18:30");
    expect(timeLabel(e, "Asia/Tokyo")).toBe("09:30 (18:30 America/Chicago)");
  });
});

describe("in-app reminders", () => {
  const now = new Date("2026-11-11T00:22:00Z"); // 18:22 in Chicago, 8 minutes before
  it("are off unless turned on", () => {
    expect(dueReminders([entry({})], now, settings({ reminders: false }), "America/Chicago", new Set())).toEqual([]);
    expect(dueReminders([entry({})], now, settings(), "America/Chicago", new Set())).toHaveLength(1);
  });
  it("skip what's done, cancelled, all-day, too far off, past, or already shown", () => {
    const s = settings();
    expect(dueReminders([entry({ done_at: "2026-11-10T20:00:00Z" })], now, s, "America/Chicago", new Set())).toEqual([]);
    expect(dueReminders([entry({ status: "cancelled" })], now, s, "America/Chicago", new Set())).toEqual([]);
    expect(dueReminders([entry({ all_day: true, starts_at: null })], now, s, "America/Chicago", new Set())).toEqual([]);
    expect(dueReminders([entry({ starts_at: "2026-11-11T01:30:00Z" })], now, s, "America/Chicago", new Set())).toEqual([]);
    expect(dueReminders([entry({ starts_at: "2026-11-11T00:10:00Z" })], now, s, "America/Chicago", new Set())).toEqual([]);
    expect(dueReminders([entry({})], now, s, "America/Chicago", new Set([reminderKey(entry({}))]))).toEqual([]);
    // A moved entry (new sequence) can remind again.
    expect(dueReminders([entry({ sequence: 1 })], now, s, "America/Chicago", new Set([reminderKey(entry({}))]))).toHaveLength(1);
  });
  it("respect quiet hours, including ones that cross midnight", () => {
    expect(inQuietHours(now, { quiet_start: "18:00", quiet_end: "19:00" }, "America/Chicago")).toBe(true);
    expect(inQuietHours(now, { quiet_start: "22:00", quiet_end: "07:00" }, "America/Chicago")).toBe(false);
    expect(inQuietHours(new Date("2026-11-11T05:00:00Z"), { quiet_start: "22:00", quiet_end: "07:00" }, "America/Chicago")).toBe(true); // 23:00
    expect(dueReminders([entry({})], now, settings({ quiet_start: "18:00", quiet_end: "19:00" }), "America/Chicago", new Set())).toEqual([]);
  });
});
