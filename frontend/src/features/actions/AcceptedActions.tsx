import { useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { DisputedNote } from "@/features/plan/DisputedNote";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { invalidateActionViews, useActions } from "@/api/queries";
import type { AcceptedAction } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";
import { VersionConflict } from "@/components/VersionConflict";
import { formatDay } from "@/features/applications/dates";
import { savedVersion } from "@/lib/conflict";
import { useRequestKey } from "@/lib/requestKey";

/**
 * Improvements you accepted (docs/ACCEPTED_ACTIONS.md), shown beside the plan, not inside it: the
 * plan keeps adapting to your practice as before. Each is one action: its occurrences are on your
 * schedule and it can sit on a kit's checklist, all by its id, so marking it done here, there or
 * in the kit is the same thing. Saying it's done is your word; it changes no score.
 */
export function AcceptedActions() {
  const actions = useActions();
  const ids = useId();
  if (actions.isPending) return null;
  if (actions.isError) return <InlineError error={actions.error} />;
  const open = actions.data.filter((a) => a.status === "open");
  const done = actions.data.filter((a) => a.status === "done");
  return (
    <section id="accepted-actions" className="card stack-sm accepted-actions" aria-labelledby={`${ids}-title`}>
      <h2 className="section-title" id={`${ids}-title`}>Improvements you accepted ({open.length})</h2>
      {actions.data.length === 0 ? (
        <p className="subtle">None yet. Accept an improvement from an interview review and it shows here, on your schedule and in an interview kit's checklist.</p>
      ) : (
        <>
          <p className="subtle">Beside your plan, not part of it. Marking one done is your word: it changes no score.</p>
          {open.length > 0 && <ul className="accepted-actions__list">{open.map((a) => <ActionCard key={a.id} a={a} />)}</ul>}
          {done.length > 0 && (
            <details>
              <summary>Done ({done.length})</summary>
              <ul className="accepted-actions__list">{done.map((a) => <ActionCard key={a.id} a={a} />)}</ul>
            </details>
          )}
        </>
      )}
    </section>
  );
}

function ActionCard({ a }: { a: AcceptedAction }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [editing, setEditing] = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const live = a.occurrences.filter((o) => o.status !== "cancelled");
  const weekly = a.recurrence === "weekly";
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      invalidateActionViews(qc);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const from = a.source.interview_date ? ` on ${formatDay(a.source.interview_date.slice(0, 10))}` : "";
  return (
    <li className="stack-sm accepted-action">
      <h3 className="accepted-action__title">
        {a.title}
        {a.status === "done" && <>{" "}<Badge tone="success">Done</Badge></>}
        {weekly && <>{" "}<Badge>Weekly</Badge></>}
      </h3>
      <p className="subtle">
        From your {a.source.interview_title}{from}: “{a.source.label}”.
        {!a.source.available && " That interview is no longer available; this is what its feedback said."}
      </p>
      <p className="accepted-action__why">{a.source.why}</p>
      <DisputedNote note={a.disputed} kept />
      {(a.source.versions ?? []).length > 0 && (
        <p className="subtle">Answered on: {(a.source.versions ?? []).map((v) => `${v.question} (question version ${v.version})`).join("; ")}.</p>
      )}
      {a.notes && <p>{a.notes}</p>}
      {a.attempts_since !== null && a.attempts_since !== undefined && (
        <p className="subtle">
          {a.attempts_since === 0 ? "Not practised since you accepted it." : `Practised ${a.attempts_since} time${a.attempts_since === 1 ? "" : "s"} since you accepted it.`}
        </p>
      )}
      {!weekly && live[0] && (
        <p className="subtle">On your schedule: {formatDay(live[0].on_date)}. <Link to="/schedule">Move it on your schedule</Link></p>
      )}
      {weekly && live.length > 0 && (
        <ul className="accepted-action__weeks">
          {live.map((o) => (
            <li key={o.id}>
              <label className="checkbox">
                <input type="checkbox" checked={!!o.completed_at} disabled={busy}
                  onChange={() => void run(() => api.setOccurrenceDone(a.id, o.id, !o.completed_at))} />
                Week of {formatDay(o.on_date)}
              </label>
            </li>
          ))}
        </ul>
      )}
      <span className="row">
        {a.practice_href && <Link className="btn btn--secondary btn--sm" to={a.practice_href}>{a.practice_label ?? "Practise it"}</Link>}
        {!weekly && (
          <Button size="sm" loading={busy} aria-label={`${a.status === "done" ? "Mark not done" : "Mark done"}: ${a.title}`}
            onClick={() => void run(() => api.setActionDone(a.id, a.status !== "done"))}>
            {a.status === "done" ? "Mark not done" : "Mark done"}
          </Button>
        )}
        {(weekly || live.length === 0) && (
          <Button size="sm" variant="ghost" aria-expanded={scheduling} onClick={() => setScheduling((v) => !v)}>
            {weekly ? "Add weeks to your schedule" : "Schedule it"}
          </Button>
        )}
        <Button size="sm" variant="ghost" aria-expanded={editing} aria-label={`Edit: ${a.title}`} onClick={() => setEditing((v) => !v)}>Edit</Button>
      </span>
      {scheduling && <ScheduleForm a={a} onDone={() => setScheduling(false)} />}
      {editing && <EditForm key={a.revision} a={a} onDone={() => setEditing(false)} />}
      <InlineError error={error} />
    </li>
  );
}

const tomorrow = () => {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

function ScheduleForm({ a, onDone }: { a: AcceptedAction; onDone: () => void }) {
  const qc = useQueryClient();
  const ids = useId();
  const [onDate, setOnDate] = useState(tomorrow);
  const [weeks, setWeeks] = useState(4);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // One key per exact request: sending it again after a lost reply returns what it made.
  const key = useRequestKey();
  const weekly = a.recurrence === "weekly";
  return (
    <form className="stack-sm" onSubmit={async (e) => {
      e.preventDefault();
      setBusy(true);
      setError(null);
      const body = { on_date: onDate, all_day: true, duration_min: 30, weeks: weekly ? weeks : 1 };
      try {
        await api.scheduleAction(a.id, { ...body, client_request_id: key.keyFor([a.id, body]) });
        key.done();
        invalidateActionViews(qc);
        onDone();
      } catch (err) {
        setError(err);
      } finally {
        setBusy(false);
      }
    }}>
      <label className="field" htmlFor={`${ids}-date`}>
        <span className="field__label">{weekly ? "First week, on" : "On"}</span>
        <input id={`${ids}-date`} type="date" required value={onDate} onChange={(e) => setOnDate(e.target.value)} />
      </label>
      {weekly && (
        <label className="field" htmlFor={`${ids}-weeks`}>
          <span className="field__label">For how many weeks</span>
          <select id={`${ids}-weeks`} value={weeks} onChange={(e) => setWeeks(Number(e.target.value))}>
            {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      )}
      <p className="subtle">All day on your schedule; set a time there if you want one. Moving it later keeps it the same entry.</p>
      <span className="row">
        <Button type="submit" size="sm" variant="primary" loading={busy}>Add to schedule</Button>
        <Button size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </span>
      <InlineError error={error} />
    </form>
  );
}

function EditForm({ a, onDone }: { a: AcceptedAction; onDone: () => void }) {
  const qc = useQueryClient();
  const ids = useId();
  const [title, setTitle] = useState(a.title);
  const [notes, setNotes] = useState(a.notes);
  const [weekly, setWeekly] = useState(a.recurrence === "weekly");
  // Once or weekly can change only before anything is on the schedule and while it isn't done.
  const canChangeRepeat = a.status !== "done" && a.occurrences.every((o) => o.status === "cancelled");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // A save refused because the action changed elsewhere: the saved one, shown beside this one.
  const [conflict, setConflict] = useState<AcceptedAction | null>(null);
  const key = useRequestKey();
  async function save(against: number) {
    setBusy(true);
    setError(null);
    const body = { title, notes, expected_revision: against, ...(canChangeRepeat ? { recurrence: weekly ? "weekly" as const : "once" as const } : {}) };
    try {
      await api.updateAction(a.id, { ...body, client_request_id: key.keyFor([a.id, body]) });
      key.done();
      setConflict(null);
      invalidateActionViews(qc);
      onDone();
    } catch (e) {
      if (e instanceof ApiError && e.code === "stale_revision") {
        setConflict(savedVersion<AcceptedAction>(e.details) ?? (await api.action(a.id).catch(() => null)));
      } else {
        setError(e);
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); void save(a.revision); }}>
      <label className="field" htmlFor={`${ids}-title`}>
        <span className="field__label">Name</span>
        <input id={`${ids}-title`} required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label className="field" htmlFor={`${ids}-notes`}>
        <span className="field__label">Your notes</span>
        <textarea id={`${ids}-notes`} rows={3} maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      {canChangeRepeat && (
        <label className="checkbox">
          <input type="checkbox" checked={weekly} onChange={(e) => setWeekly(e.target.checked)} />
          Every week (each week's occurrence is done on its own)
        </label>
      )}
      {conflict && (
        <VersionConflict what="action" savedWhen={`version ${conflict.revision}`} busy={busy}
          fields={[{ label: "Name", mine: title, saved: conflict.title }, { label: "Notes", mine: notes, saved: conflict.notes }]}
          onKeepMine={() => void save(conflict.revision)}
          onUseSaved={() => { setTitle(conflict.title); setNotes(conflict.notes); setConflict(null); invalidateActionViews(qc); onDone(); }} />
      )}
      <span className="row">
        <Button type="submit" size="sm" variant="primary" loading={busy}>Save</Button>
        <Button size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </span>
      <InlineError error={error} />
    </form>
  );
}
