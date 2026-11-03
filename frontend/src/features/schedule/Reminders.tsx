import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useSchedule, useScheduleSettings } from "@/api/queries";
import type { ScheduleEntry } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { browserTimeZone, todayIn } from "@/features/applications/dates";

import { dueReminders, reminderKey } from "./reminders";
import { addDays, timeLabel } from "./time";

const SHOWN_KEY = "codecoach.reminders.shown";

function readShown(): Set<string> {
  try {
    return new Set(JSON.parse(sessionStorage.getItem(SHOWN_KEY) ?? "[]") as string[]);
  } catch {
    return new Set();
  }
}

/**
 * In-app reminders: checked on this device every 30 seconds while CodeCoach is open, only when
 * the learner turned them on. Each reminder shows once per version of an entry (moving it can
 * remind again). Nothing is sent anywhere.
 */
export function Reminders() {
  const { isAuthenticated } = useAuth();
  const settings = useScheduleSettings(isAuthenticated);
  const on = isAuthenticated && !!settings.data?.reminders;
  const tz = settings.data?.timezone ?? browserTimeZone();
  const today = todayIn(tz);
  const entries = useSchedule(today, addDays(today, 1), false, on, 60_000);
  const [tick, setTick] = useState(0);
  const [shown, setShown] = useState<Set<string>>(readShown);

  // Re-check every 30 seconds; the clock is read fresh each time, never a stale copy.
  useEffect(() => {
    if (!on) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 30_000);
    return () => window.clearInterval(id);
  }, [on]);
  const now = useMemo(() => new Date(), [tick, entries.data, on]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!on || !settings.data || !entries.data) return null;
  const due = dueReminders(entries.data, now, settings.data, tz, shown);
  const dismiss = (e: ScheduleEntry) => {
    const next = new Set(shown).add(reminderKey(e));
    setShown(next);
    try { sessionStorage.setItem(SHOWN_KEY, JSON.stringify([...next])); } catch { /* storage blocked: shown again after a reload */ }
  };
  return (
    <div className="reminders" role="status" aria-live="polite">
      {due.map((e) => {
        const minutes = Math.max(0, Math.round((new Date(e.starts_at!).getTime() - now.getTime()) / 60_000));
        return (
          <div key={reminderKey(e)} className="reminder">
            <span><strong>{minutes === 0 ? "Starting now" : `In ${minutes} ${minutes === 1 ? "minute" : "minutes"}`}:</strong> {e.title} <span className="subtle">({timeLabel(e, tz)}, {e.duration_min} min)</span></span>
            <span className="row">
              {e.href && <Link to={e.href} onClick={() => dismiss(e)}>Open</Link>}
              <Button size="sm" variant="ghost" onClick={() => dismiss(e)}>Dismiss</Button>
            </span>
          </div>
        );
      })}
    </div>
  );
}
