import { useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useSchedule, useSchedulable, useScheduleSettings } from "@/api/queries";
import type { ScheduleEntry, ScheduleKind, ScheduleSettings } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { browserTimeZone, formatDay, todayIn } from "@/features/applications/dates";

import { addDays, entryDay, startOfWeek, timeLabel, TIME_ZONES, zoneLabel } from "./time";

/** Your schedule: existing activities on dates and times you choose, in your schedule's time zone. */
export function SchedulePage() {
  const settings = useScheduleSettings();
  if (settings.isPending) return <LoadingState label="Loading your schedule…" />;
  if (settings.isError) return <div className="page"><ErrorState error={settings.error} onRetry={() => void settings.refetch()} /></div>;
  return <Schedule settings={settings.data} />;
}

function Schedule({ settings }: { settings: ScheduleSettings }) {
  const device = browserTimeZone();
  const tz = settings.timezone ?? device;
  const [params, setParams] = useSearchParams();
  const today = todayIn(tz);
  const weekStart = startOfWeek(params.get("week") ?? today);
  const weekEnd = addDays(weekStart, 6);
  const showCancelled = params.get("cancelled") === "1";
  const entries = useSchedule(weekStart, weekEnd, showCancelled);
  const [status, setStatus] = useState("");
  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v);
    else p.delete(k);
    setParams(p, { replace: true });
  };
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const byDay = new Map(days.map((d) => [d, [] as ScheduleEntry[]]));
  for (const e of entries.data ?? []) byDay.get(entryDay(e, tz))?.push(e);
  for (const list of byDay.values()) list.sort((a, b) => (a.all_day === b.all_day ? (a.starts_at ?? "").localeCompare(b.starts_at ?? "") : a.all_day ? -1 : 1));
  const titles = new Map((entries.data ?? []).map((e) => [e.id, e.title]));

  async function downloadWeek() {
    await download({ from: weekStart, to: weekEnd }, `codecoach-week-${weekStart}.ics`);
    setStatus("Downloaded. Open the file with your calendar app to import it.");
  }

  return (
    <div className="page schedule-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">SCHEDULE</p>
          <h1 className="page__title">Your schedule</h1>
          <p className="page__subtitle">Time you set aside for your practice. Scheduling something isn't doing it: an entry shows as done only when the activity itself is.</p>
        </div>
      </div>

      <TimeZoneCard settings={settings} device={device} />
      <AddEntry tz={tz} defaultDate={today} />

      <section className="stack-sm" aria-labelledby="week-title">
        <div className="schedule-week__nav">
          <h2 className="section-title" id="week-title">Week of {formatDay(weekStart)}</h2>
          <span className="row">
            <Button size="sm" variant="ghost" onClick={() => set("week", addDays(weekStart, -7))}>Previous week</Button>
            <Button size="sm" variant="ghost" onClick={() => set("week", "")}>This week</Button>
            <Button size="sm" variant="ghost" onClick={() => set("week", addDays(weekStart, 7))}>Next week</Button>
          </span>
        </div>
        <p className="subtle">Times are in {zoneLabel(tz)}.</p>
        <span className="row">
          <label className="checkbox"><input type="checkbox" checked={showCancelled} onChange={(e) => set("cancelled", e.target.checked ? "1" : "")} />Show cancelled</label>
          <Button size="sm" onClick={() => void downloadWeek()}>Download this week (.ics)</Button>
        </span>
        <p className="subtle">A downloaded file copies these events into your calendar once. Changes you make here later may not reach it: download again after a change (some calendars then update the same events, others add copies). CodeCoach doesn't connect to or change your calendar.</p>
        <p className="subtle" role="status">{status}</p>
        {entries.isPending ? <LoadingState label="Loading the week…" /> : entries.isError ? <ErrorState error={entries.error} onRetry={() => void entries.refetch()} /> : (
          <ol className="schedule-days">
            {days.map((d) => (
              <li key={d} className={`schedule-day${d === today ? " schedule-day--today" : ""}`}>
                <h3 className="schedule-day__title">{formatDay(d)}{d === today ? <Badge tone="info">Today</Badge> : null}</h3>
                {byDay.get(d)!.length === 0 ? <p className="subtle">Nothing scheduled.</p> : (
                  <ul className="schedule-entries">
                    {byDay.get(d)!.map((e) => <Entry key={e.id} e={e} tz={tz} titles={titles} />)}
                  </ul>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
      <RemindersCard settings={settings} tz={tz} />
    </div>
  );
}

async function download(query: { ids?: string; from?: string; to?: string }, filename: string) {
  const text = await api.scheduleIcs(query);
  const url = URL.createObjectURL(new Blob([text], { type: "text/calendar;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function Entry({ e, tz, titles }: { e: ScheduleEntry; tz: string; titles: Map<string, string> }) {
  const qc = useQueryClient();
  const [moving, setMoving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["me", "schedule"] });
  return (
    <li className={`schedule-entry${e.status === "cancelled" ? " schedule-entry--cancelled" : ""}`}>
      <span className="schedule-entry__time">{e.all_day ? "All day" : timeLabel(e, tz)}</span>
      <span className="schedule-entry__body">
        {e.href && e.available ? <Link to={e.href}>{e.title}</Link> : <span>{e.title}</span>}
        <span className="subtle"> · {e.duration_min} min</span>
        {e.done_at && <Badge tone="success">Done</Badge>}
        {e.status === "cancelled" && <Badge tone="warning">Cancelled</Badge>}
        {!e.available && <span className="subtle"> · No longer available</span>}
        {e.conflicts.length > 0 && <span className="schedule-entry__conflict">Overlaps with {e.conflicts.map((c) => titles.get(c) ?? "another entry").join(", ")}. Nothing was moved; change one if you need to.</span>}
        {e.notes && <span className="subtle">{e.notes}</span>}
        {e.kind === "application_event" && e.status === "scheduled" && (
          <span className="subtle schedule-entry__follow">
            {e.follows_interview
              ? "Kept relative to the interview: if it moves, you'll be offered the same time before it (nothing moves until you confirm)."
              : "A fixed time: it stays here if the interview moves."}
          </span>
        )}
      </span>
      {e.status === "scheduled" && (
        <span className="row schedule-entry__actions">
          <Button size="sm" variant="ghost" aria-expanded={moving} onClick={() => setMoving((v) => !v)}>Move</Button>
          <Button size="sm" variant="ghost" onClick={async () => {
            if (!window.confirm(`Cancel “${e.title}”?`)) return;
            setError(null);
            try { await api.cancelScheduleEntry(e.id); refresh(); } catch (err) { setError(err); }
          }}>Cancel</Button>
          <Button size="sm" variant="ghost" onClick={() => void download({ ids: e.id }, `codecoach-${e.on_date}.ics`)}>.ics</Button>
          {e.kind === "application_event" && !e.all_day && e.available && (
            <Button size="sm" variant="ghost" onClick={async () => {
              setError(null);
              try { await api.followInterview(e.id, !e.follows_interview, e.sequence); refresh(); } catch (err) { setError(err); }
            }}>{e.follows_interview ? "Keep it at a fixed time" : "Keep it relative to the interview"}</Button>
          )}
        </span>
      )}
      {moving && <TimeForm tz={e.timezone ?? tz} initial={e} submitLabel="Save new time" onSubmit={async (t) => { await api.moveScheduleEntry(e.id, t); setMoving(false); refresh(); }} onCancel={() => setMoving(false)} />}
      <InlineError error={error} />
    </li>
  );
}

export interface TimeChoice {
  on_date: string;
  all_day: boolean;
  local_time: string | null;
  timezone: string | null;
  fold: number | null;
  duration_min: number;
}

function TimeForm({ tz, initial, submitLabel, onSubmit, onCancel, children, disabled }: {
  tz: string; initial?: Partial<ScheduleEntry>; submitLabel: string; onSubmit: (t: TimeChoice) => Promise<void>;
  onCancel?: () => void; children?: React.ReactNode; disabled?: boolean;
}) {
  const id = useId();
  const [form, setForm] = useState({
    on_date: initial?.on_date ?? todayIn(tz), all_day: initial?.all_day ?? false, local_time: initial?.local_time ?? "18:00",
    timezone: initial?.timezone ?? tz, duration_min: initial?.duration_min ?? 30,
  });
  const [fold, setFold] = useState<0 | 1 | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const ambiguous = error instanceof ApiError && error.code === "ambiguous_time" ? (error.details as { first_offset: string; second_offset: string }) : null;
  const set = (k: keyof typeof form, v: string | number | boolean) => { setForm((f) => ({ ...f, [k]: v })); setFold(null); setError(null); };
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ on_date: form.on_date, all_day: form.all_day, local_time: form.all_day ? null : form.local_time, timezone: form.all_day ? null : form.timezone, fold, duration_min: form.duration_min });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  const off = (o: string) => `UTC${o.replace(/(\d\d)(\d\d)$/, "$1:$2")}`;
  return (
    <form className="stack-sm schedule-form" onSubmit={(e) => void submit(e)} aria-label={submitLabel}>
      {children}
      <div className="app-form__grid">
        <label className="field"><span className="field__label">Date</span>
          <input className="input" type="date" required value={form.on_date} onChange={(e) => set("on_date", e.target.value)} />
        </label>
        <label className="checkbox"><input type="checkbox" checked={form.all_day} onChange={(e) => set("all_day", e.target.checked)} />All day (no set time)</label>
        {!form.all_day && (
          <>
            <label className="field"><span className="field__label">Start time</span><input className="input" type="time" required value={form.local_time} onChange={(e) => set("local_time", e.target.value)} /></label>
            <label className="field"><span className="field__label">Time zone</span>
              <select className="select" value={form.timezone} onChange={(e) => set("timezone", e.target.value)}>
                {(TIME_ZONES.includes(form.timezone) ? TIME_ZONES : [form.timezone, ...TIME_ZONES]).map((z) => <option key={z} value={z}>{zoneLabel(z)}</option>)}
              </select>
            </label>
          </>
        )}
        <label className="field"><span className="field__label">Length</span>
          <select className="select" value={form.duration_min} onChange={(e) => set("duration_min", Number(e.target.value))}>
            {[10, 15, 20, 30, 45, 60, 90, 120].map((m) => <option key={m} value={m}>{m} minutes</option>)}
          </select>
        </label>
      </div>
      {ambiguous ? (
        <fieldset className="stack-sm banner banner--warning">
          <legend>{(error as ApiError).message}</legend>
          <label className="checkbox"><input type="radio" name={`${id}-fold`} checked={fold === 0} onChange={() => setFold(0)} />The first one ({off(ambiguous.first_offset)})</label>
          <label className="checkbox"><input type="radio" name={`${id}-fold`} checked={fold === 1} onChange={() => setFold(1)} />The second one ({off(ambiguous.second_offset)})</label>
        </fieldset>
      ) : <InlineError error={error} />}
      <span className="row">
        <Button type="submit" size="sm" variant="primary" loading={busy} disabled={disabled || (!!ambiguous && fold === null)}>{submitLabel}</Button>
        {onCancel && <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>}
      </span>
    </form>
  );
}

const KIND_LABEL: Record<ScheduleKind, string> = {
  plan_item: "Plan step", review_item: "Review", question: "Question", problem: "Coding problem", application_event: "Interview preparation", drill: "Communication drill",
};

function AddEntry({ tz, defaultDate }: { tz: string; defaultDate: string }) {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const schedulable = useSchedulable();
  const preset = params.get("kind") && params.get("ref") ? { kind: params.get("kind") as ScheduleKind, ref: params.get("ref")!, title: params.get("title") ?? "" } : null;
  const [choice, setChoice] = useState(preset ? `${preset.kind}|${preset.ref}` : "");
  const [notes, setNotes] = useState("");
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const [added, setAdded] = useState("");
  const options = [...(preset ? [{ kind: preset.kind, ref: preset.ref, title: preset.title || preset.ref, detail: KIND_LABEL[preset.kind], minutes: null }] : []),
    ...(schedulable.data ?? []).filter((s) => !(preset && s.kind === preset.kind && s.ref === preset.ref))];
  const [kind, ref] = choice ? (choice.split("|") as [ScheduleKind, string]) : [null, null];
  return (
    <Card className="stack-sm">
      <h2 className="section-title">Schedule something</h2>
      <TimeForm key={requestId} tz={tz} initial={{ on_date: defaultDate }} submitLabel="Add to schedule" disabled={!kind}
        onSubmit={async (t) => {
          const e = await api.createScheduleEntry({ kind: kind!, ref: ref!, ...t, notes, client_request_id: requestId });
          setAdded(`Added “${e.title}” on ${formatDay(e.on_date)}.`);
          setChoice("");
          setNotes("");
          setRequestId(crypto.randomUUID());
          if (preset) setParams({}, { replace: true });
          void qc.invalidateQueries({ queryKey: ["me", "schedule"] });
        }}>
        <label className="field"><span className="field__label">What</span>
          <select className="select" value={choice} onChange={(e) => setChoice(e.target.value)}>
            <option value="">Choose from your plan, reviews and interviews…</option>
            {options.map((o) => <option key={`${o.kind}|${o.ref}`} value={`${o.kind}|${o.ref}`}>{o.title} ({KIND_LABEL[o.kind]})</option>)}
          </select>
        </label>
        {options.length === 0 && !schedulable.isPending && <p className="subtle">Nothing to choose yet: start a <Link to="/plan">plan</Link>, save questions for review, or add an interview to an <Link to="/applications">application</Link>. You can also schedule any question or problem from its page.</p>}
        <label className="field"><span className="field__label">Note <span className="subtle">(optional)</span></span><input className="input" maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
      </TimeForm>
      <p className="subtle" role="status">{added}</p>
    </Card>
  );
}

function TimeZoneCard({ settings, device }: { settings: ScheduleSettings; device: string }) {
  const qc = useQueryClient();
  const [tz, setTz] = useState(settings.timezone ?? device);
  const [error, setError] = useState<unknown>(null);
  const save = async (zone: string) => {
    setError(null);
    try { qc.setQueryData(["me", "schedule", "settings"], await api.saveScheduleSettings({ timezone: zone })); } catch (e) { setError(e); }
  };
  return (
    <Card className="stack-sm">
      <h2 className="section-title">Time zone</h2>
      {settings.timezone
        ? <p>Your schedule shows times in <strong>{zoneLabel(settings.timezone)}</strong>.</p>
        : <p>Your schedule uses this device's time zone, <strong>{zoneLabel(device)}</strong>, until you choose one.</p>}
      {settings.timezone && settings.timezone !== device && (
        <div className="banner banner--info stack-sm" role="status">
          <span>This device is set to {zoneLabel(device)}. Timed entries stay at the same moment wherever you are; only how they're shown changes. All-day entries keep their date.</span>
          <span><Button size="sm" onClick={() => void save(device)}>Show times in {zoneLabel(device)}</Button></span>
        </div>
      )}
      <form className="row" onSubmit={(e) => { e.preventDefault(); void save(tz); }}>
        <label className="field"><span className="field__label">Schedule time zone</span>
          <select className="select" value={tz} onChange={(e) => setTz(e.target.value)}>
            {(TIME_ZONES.includes(tz) ? TIME_ZONES : [tz, ...TIME_ZONES]).map((z) => <option key={z} value={z}>{zoneLabel(z)}</option>)}
          </select>
        </label>
        <Button type="submit" size="sm" disabled={tz === settings.timezone}>Use this time zone</Button>
      </form>
      <InlineError error={error} />
    </Card>
  );
}

function RemindersCard({ settings, tz }: { settings: ScheduleSettings; tz: string }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ reminders: settings.reminders, reminder_minutes: settings.reminder_minutes, quiet_start: settings.quiet_start ?? "", quiet_end: settings.quiet_end ?? "" });
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      qc.setQueryData(["me", "schedule", "settings"], await api.saveScheduleSettings({ timezone: settings.timezone ?? tz, ...form }));
      setSaved(true);
    } catch (err) {
      setError(err);
    }
  }
  return (
    <form className="card stack-sm" aria-label="Reminders" onSubmit={(e) => void submit(e)}>
      <h2 className="section-title">Reminders</h2>
      <p className="subtle">Reminders appear only inside CodeCoach, while it's open in a browser tab. CodeCoach doesn't send emails, push notifications or calendar invitations, and doesn't remind you about anything you've already done.</p>
      <label className="checkbox"><input type="checkbox" checked={form.reminders} onChange={(e) => { setForm({ ...form, reminders: e.target.checked }); setSaved(false); }} />Show reminders while CodeCoach is open</label>
      <div className="app-form__grid">
        <label className="field"><span className="field__label">How long before</span>
          <select className="select" value={form.reminder_minutes} onChange={(e) => { setForm({ ...form, reminder_minutes: Number(e.target.value) }); setSaved(false); }}>
            {[0, 5, 10, 15, 30, 60].map((m) => <option key={m} value={m}>{m === 0 ? "At the start time" : `${m} minutes`}</option>)}
          </select>
        </label>
        <label className="field"><span className="field__label">Quiet from</span><input className="input" type="time" value={form.quiet_start} onChange={(e) => { setForm({ ...form, quiet_start: e.target.value }); setSaved(false); }} /></label>
        <label className="field"><span className="field__label">Quiet until</span><input className="input" type="time" value={form.quiet_end} onChange={(e) => { setForm({ ...form, quiet_end: e.target.value }); setSaved(false); }} /></label>
      </div>
      <p className="subtle">Quiet hours are in {zoneLabel(settings.timezone ?? tz)}. Leave them empty for none.</p>
      <InlineError error={error} />
      <span className="row"><Button type="submit" size="sm">Save reminders</Button>{saved && <span className="subtle" role="status">Saved.</span>}</span>
    </form>
  );
}
