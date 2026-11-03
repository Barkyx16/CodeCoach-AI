import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useApplication, useStories, useTargets } from "@/api/queries";
import type { Application, ApplicationEvent, ApplicationStage, EventKind } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { formatDateTime } from "@/lib/format";

import { browserTimeZone, describeWhen } from "./dates";
import { ScheduleLink } from "@/features/schedule/ScheduleLink";

import { DraftComposer } from "./DraftComposer";
import { EVENT_KIND_LABEL, STAGE_HINT, STAGE_LABEL, STAGES } from "./labels";

export function ApplicationPage() {
  const { id = "" } = useParams();
  const app = useApplication(id);
  if (app.isPending) return <LoadingState label="Loading the application…" />;
  if (app.isError) return <div className="page"><ErrorState error={app.error} onRetry={() => void app.refetch()} /></div>;
  return <Detail key={app.data.id} a={app.data} />;
}

function Detail({ a }: { a: Application }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const done = (next: Application) => {
    qc.setQueryData(["me", "application", next.id], next);
    void qc.invalidateQueries({ queryKey: ["me", "applications"] });
  };
  return (
    <div className="page application-page">
      <BackLink fallback={{ to: "/applications", label: "Your applications" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">APPLICATION{a.archived ? " · ARCHIVED" : ""}</p>
          <h1 className="page__title">{a.role_title}</h1>
          <p className="row"><span>{a.employer}</span><Badge>{STAGE_LABEL[a.stage]}</Badge></p>
        </div>
      </div>
      <div className="application-page__layout">
        <div className="stack">
          <StageCard a={a} onDone={done} />
          <EventsCard a={a} onDone={done} />
          <DetailsCard a={a} onDone={done} />
          <DraftComposer role={a.role_title} employer={a.employer} />
        </div>
        <aside className="stack">
          <PrepareCard a={a} />
          <LinksCard a={a} onDone={done} />
          <Card className="stack-sm">
            <h2 className="section-title">Keep or remove</h2>
            <p className="subtle">Archiving hides it from your board; nothing is lost. Deleting removes it, its events and its history.</p>
            <span className="row">
              <Button size="sm" onClick={async () => done(await api.archiveApplication(a.id, !a.archived))}>{a.archived ? "Unarchive" : "Archive"}</Button>
              <Button size="sm" variant="danger" onClick={async () => {
                if (!window.confirm(`Delete ${a.role_title} at ${a.employer}, its events and its history? This can't be undone. (Archive keeps it out of the way instead.)`)) return;
                await api.deleteApplication(a.id);
                void qc.invalidateQueries({ queryKey: ["me", "applications"] });
                navigate("/applications", { replace: true });
              }}>Delete…</Button>
            </span>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function StageCard({ a, onDone }: { a: Application; onDone: (a: Application) => void }) {
  const [to, setTo] = useState<ApplicationStage>(a.stage);
  const [note, setNote] = useState("");
  const [correction, setCorrection] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const sent = { stage: to, note, correction };
    try {
      onDone(await api.setApplicationStage(a.id, sent));
      // Clear only what was sent: anything typed or ticked while it was saving stays.
      setNote((n) => (n === sent.note ? "" : n));
      setCorrection((c) => (c === sent.correction ? false : c));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card className="stack-sm">
      <h2 className="section-title">Stage</h2>
      <p>{STAGE_LABEL[a.stage]} <span className="subtle">· {STAGE_HINT[a.stage]}</span></p>
      <form className="stack-sm" onSubmit={(e) => void submit(e)} aria-label="Change the stage">
        <div className="app-form__grid">
          <label className="field"><span className="field__label">Move to</span>
            <select className="select" value={to} onChange={(e) => setTo(e.target.value as ApplicationStage)}>
              {STAGES.map((s) => <option key={s} value={s}>{STAGE_LABEL[s]}</option>)}
            </select>
          </label>
          <label className="field"><span className="field__label">Note <span className="subtle">(optional)</span></span>
            <input className="input" maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
        </div>
        <label className="checkbox"><input type="checkbox" checked={correction} onChange={(e) => setCorrection(e.target.checked)} />This corrects a mistake (it wasn't a real change)</label>
        <InlineError error={error} />
        <span><Button type="submit" size="sm" variant="primary" loading={busy} disabled={to === a.stage}>Save stage</Button></span>
      </form>
      <h3 className="section-title">History</h3>
      <ol className="stage-history">
        {a.history.map((h, i) => (
          <li key={i}>
            {h.from_stage ? <>{STAGE_LABEL[h.from_stage]} → {STAGE_LABEL[h.to_stage]}</> : <>Added as {STAGE_LABEL[h.to_stage]}</>}
            {h.correction && <Badge tone="warning">Correction</Badge>}
            <span className="subtle"> · {formatDateTime(h.changed_at)}</span>
            {(h.role_title !== a.role_title || h.employer !== a.employer) && <span className="subtle"> · then: {h.role_title}, {h.employer}</span>}
            {h.note && <p className="subtle">{h.note}</p>}
          </li>
        ))}
      </ol>
    </Card>
  );
}

const TIME_ZONES = (() => {
  try {
    return (Intl as unknown as { supportedValuesOf(k: string): string[] }).supportedValuesOf("timeZone");
  } catch {
    return [] as string[];
  }
})();

function EventsCard({ a, onDone }: { a: Application; onDone: (a: Application) => void }) {
  const [editing, setEditing] = useState<ApplicationEvent | "new" | null>(null);
  return (
    <Card className="stack-sm">
      <h2 className="section-title">Interviews and other events</h2>
      {a.events.length === 0 && <p className="subtle">None yet. Each interview is recorded as its own event.</p>}
      <ul className="event-list">
        {a.events.map((e) => editing !== e && (
          <li key={e.id} className="event-list__item">
            <strong>{e.title}</strong> <Badge>{EVENT_KIND_LABEL[e.kind]}</Badge>
            <span className="subtle"> · {describeWhen(e)}</span>
            {e.notes && <p className="subtle">{e.notes}</p>}
            <span className="row">
              <Button size="sm" variant="ghost" onClick={() => setEditing(e)}>Edit</Button>
              <Link to={`/applications/${a.id}/events/${e.id}/kit`}>Interview-day kit</Link>
              <Link to={`/applications/${a.id}/events/${e.id}/reflection`}>Reflect on this interview</Link>
              <ScheduleLink kind="application_event" refId={e.id} title={`Prepare: ${e.title} (${a.employer})`} label="Schedule preparation time" />
              <Button size="sm" variant="ghost" onClick={async () => { if (window.confirm(`Remove “${e.title}”?`)) onDone(await api.deleteApplicationEvent(a.id, e.id)); }}>Remove</Button>
            </span>
          </li>
        ))}
      </ul>
      {editing ? <EventForm key={editing === "new" ? "new" : editing.id} a={a} event={editing === "new" ? null : editing} onDone={(next) => { if (next) onDone(next); setEditing(null); }} />
        : <span><Button size="sm" onClick={() => setEditing("new")}>Add an event</Button></span>}
    </Card>
  );
}

function EventForm({ a, event, onDone }: { a: Application; event: ApplicationEvent | null; onDone: (a: Application | null) => void }) {
  const [form, setForm] = useState({
    kind: (event?.kind ?? "interview") as EventKind, title: event?.title ?? "", on_date: event?.on_date ?? "",
    local_time: event?.local_time ?? "", timezone: event?.timezone ?? browserTimeZone(), notes: event?.notes ?? "",
  });
  const [fold, setFold] = useState<0 | 1 | null>(null);
  const [requestId] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const ambiguous = error instanceof ApiError && error.code === "ambiguous_time" ? (error.details as { first_offset: string; second_offset: string }) : null;
  const set = (k: keyof typeof form, v: string) => { setForm((f) => ({ ...f, [k]: v })); setFold(null); };
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = {
      kind: form.kind, title: form.title, on_date: form.on_date || null, local_time: form.local_time || null,
      timezone: form.local_time ? form.timezone : null, notes: form.notes, fold, client_request_id: event ? null : requestId,
    };
    try {
      onDone(event ? await api.updateApplicationEvent(a.id, event.id, body) : await api.addApplicationEvent(a.id, body));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="stack-sm event-form" aria-label={event ? "Edit event" : "New event"} onSubmit={(e) => void submit(e)}>
      <div className="app-form__grid">
        <label className="field"><span className="field__label">What</span><input className="input" required maxLength={120} value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="Second interview, with the ward manager" /></label>
        <label className="field"><span className="field__label">Kind</span>
          <select className="select" value={form.kind} onChange={(e) => set("kind", e.target.value)}>
            {(Object.keys(EVENT_KIND_LABEL) as EventKind[]).map((k) => <option key={k} value={k}>{EVENT_KIND_LABEL[k]}</option>)}
          </select>
        </label>
        <label className="field"><span className="field__label">Date <span className="subtle">(optional)</span></span><input className="input" type="date" value={form.on_date} onChange={(e) => set("on_date", e.target.value)} /></label>
        <label className="field"><span className="field__label">Time <span className="subtle">(optional)</span></span><input className="input" type="time" value={form.local_time} disabled={!form.on_date} onChange={(e) => set("local_time", e.target.value)} /></label>
        <label className="field"><span className="field__label">Time zone</span>
          <select className="select" value={form.timezone} onChange={(e) => set("timezone", e.target.value)} disabled={!form.local_time}>
            {(TIME_ZONES.length ? TIME_ZONES : [form.timezone]).map((z) => <option key={z} value={z}>{z.replace(/_/g, " ")}</option>)}
          </select>
        </label>
      </div>
      <label className="field"><span className="field__label">Notes <span className="subtle">(optional)</span></span><textarea className="input" rows={2} maxLength={2000} value={form.notes} onChange={(e) => set("notes", e.target.value)} /></label>
      {ambiguous ? (
        <fieldset className="stack-sm banner banner--warning">
          <legend>{(error as ApiError).message}</legend>
          <label className="checkbox"><input type="radio" name="fold" checked={fold === 0} onChange={() => setFold(0)} />The first one (UTC{ambiguous.first_offset.replace(/(\d\d)(\d\d)$/, "$1:$2")})</label>
          <label className="checkbox"><input type="radio" name="fold" checked={fold === 1} onChange={() => setFold(1)} />The second one (UTC{ambiguous.second_offset.replace(/(\d\d)(\d\d)$/, "$1:$2")})</label>
        </fieldset>
      ) : <InlineError error={error} />}
      <span className="row">
        <Button type="submit" size="sm" variant="primary" loading={busy} disabled={!form.title.trim() || (!!ambiguous && fold === null)}>{event ? "Save event" : "Add event"}</Button>
        <Button size="sm" variant="ghost" onClick={() => onDone(null)}>Cancel</Button>
      </span>
    </form>
  );
}

function DetailsCard({ a, onDone }: { a: Application; onDone: (a: Application) => void }) {
  const [form, setForm] = useState({ role_title: a.role_title, employer: a.employer, link: a.link ?? "", applied_on: a.applied_on ?? "", next_action: a.next_action, next_action_due: a.next_action_due ?? "", notes: a.notes });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const set = (k: keyof typeof form, v: string) => { setForm((f) => ({ ...f, [k]: v })); setSaved(false); };
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const clear = (["link", "applied_on", "next_action_due"] as const).filter((k) => !form[k] && a[k]);
    try {
      onDone(await api.updateApplication(a.id, {
        role_title: form.role_title, employer: form.employer, next_action: form.next_action, notes: form.notes,
        link: form.link || null, applied_on: form.applied_on || null, next_action_due: form.next_action_due || null, clear,
      }));
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="card stack-sm" aria-label="Details" onSubmit={(e) => void submit(e)}>
      <h2 className="section-title">Details</h2>
      <div className="app-form__grid">
        <label className="field"><span className="field__label">Role title</span><input className="input" required maxLength={120} value={form.role_title} onChange={(e) => set("role_title", e.target.value)} /></label>
        <label className="field"><span className="field__label">Employer</span><input className="input" required maxLength={120} value={form.employer} onChange={(e) => set("employer", e.target.value)} /></label>
        <label className="field"><span className="field__label">Applied on</span><input className="input" type="date" value={form.applied_on} onChange={(e) => set("applied_on", e.target.value)} /></label>
        <label className="field"><span className="field__label">Link to the posting</span><input className="input" type="url" maxLength={500} value={form.link} onChange={(e) => set("link", e.target.value)} placeholder="https://" /></label>
        <label className="field"><span className="field__label">Next action</span><input className="input" maxLength={300} value={form.next_action} onChange={(e) => set("next_action", e.target.value)} /></label>
        <label className="field"><span className="field__label">Next action due</span><input className="input" type="date" value={form.next_action_due} onChange={(e) => set("next_action_due", e.target.value)} /></label>
      </div>
      {a.link && <p className="subtle">Posting: <a href={a.link} target="_blank" rel="noopener noreferrer nofollow">{a.link}<span className="visually-hidden"> (opens in a new tab)</span></a></p>}
      <label className="field"><span className="field__label">Notes <span className="subtle">(private)</span></span><textarea className="input" rows={3} maxLength={4000} value={form.notes} onChange={(e) => set("notes", e.target.value)} /></label>
      <InlineError error={error} />
      <span className="row"><Button type="submit" size="sm" variant="primary" loading={busy}>Save details</Button>{saved && <span className="subtle" role="status">Saved.</span>}</span>
    </form>
  );
}

function LinksCard({ a, onDone }: { a: Application; onDone: (a: Application) => void }) {
  const targets = useTargets();
  const stories = useStories({});
  const [error, setError] = useState<unknown>(null);
  // Shown at once; the server's answer replaces it (or it reverts, with the error, if saving fails).
  const [pending, setPending] = useState<{ target?: string; stories?: string[] } | null>(null);
  const save = async (body: Parameters<typeof api.updateApplication>[1], optimistic: { target?: string; stories?: string[] }) => {
    setError(null);
    setPending(optimistic);
    try { onDone(await api.updateApplication(a.id, body)); } catch (e) { setError(e); } finally { setPending(null); }
  };
  const target = pending?.target ?? a.target?.id ?? "";
  const linked = new Set(pending?.stories ?? a.stories.map((s) => s.id));
  return (
    <Card className="stack-sm">
      <h2 className="section-title">Linked preparation</h2>
      <label className="field"><span className="field__label">Job target</span>
        <select className="select" value={target} onChange={(e) => void save(e.target.value ? { target_id: e.target.value, clear: [] } : { clear: ["target_id"] }, { target: e.target.value })}>
          <option value="">None</option>
          {(targets.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
        </select>
      </label>
      <fieldset className="stack-sm">
        <legend className="field__label">Stories to prepare</legend>
        {(stories.data ?? []).length === 0 && <p className="subtle">No stories yet. <Link to="/stories/new">Write one</Link>.</p>}
        {(stories.data ?? []).map((s) => (
          <label key={s.id} className="checkbox">
            <input type="checkbox" checked={linked.has(s.id)} onChange={(e) => {
              const next = e.target.checked ? [...linked, s.id] : [...linked].filter((x) => x !== s.id);
              void save({ clear: [], story_ids: next }, { stories: next });
            }} />
            {s.title}
          </label>
        ))}
      </fieldset>
      <p className="subtle">Links point to your target and stories; nothing is copied.</p>
      <InlineError error={error} />
    </Card>
  );
}

/** Working "Prepare for this stage" actions that reuse existing practice. */
function PrepareCard({ a }: { a: Application }) {
  const items: { to: string; label: string }[] = [];
  if (a.target) items.push({ to: `/targets/${a.target.id}`, label: `Open the preparation map for ${a.target.title}` });
  if (a.stage === "saved" || a.stage === "applied") items.push({ to: "/stories", label: "Get your stories ready" });
  if (a.stage === "interviewing" || a.stage === "applied") {
    items.push({ to: "/interviews", label: "Do a mock interview" });
    items.push({ to: "/problems?view=questions", label: "Practise interview questions" });
  }
  for (const s of a.stories) items.push({ to: `/stories/${s.id}`, label: `Review your story “${s.title}”` });
  return (
    <Card className="stack-sm">
      <h2 className="section-title">Prepare for this stage</h2>
      {items.length === 0 ? <p className="subtle">Nothing to prepare at this stage.</p> : (
        <ul className="mini-list">{items.map((i) => <li key={i.to + i.label}><Link to={i.to} state={{ from: `/applications/${a.id}`, fromLabel: "Back to the application" }}>{i.label}</Link></li>)}</ul>
      )}
    </Card>
  );
}
