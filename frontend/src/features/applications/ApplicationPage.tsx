import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useApplication, useStories, useTargets } from "@/api/queries";
import type { Application, ApplicationEvent, ApplicationStage, EventKind } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { PrivateUnavailable } from "@/components/Unavailable";
import { isGone } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";

import { browserTimeZone, describeWhen } from "./dates";
import { ScheduleLink } from "@/features/schedule/ScheduleLink";

import { DraftComposer } from "./DraftComposer";
import { EVENT_KIND_LABEL, STAGE_HINT, STAGE_LABEL, STAGES } from "./labels";
import { PrepPanel } from "./PrepPanel";
import { externalHref } from "@/lib/links";
import { useRequestKey } from "@/lib/requestKey";
import { recoveredSave } from "@/lib/conflict";
import { useAuth } from "@/auth/useAuth";
import { VersionConflict } from "@/components/VersionConflict";
import { FormDraftOffer, FormDraftStatus } from "@/components/FormDraftNotice";
import { formDraftKey, isTextForm, useFormDraft } from "@/hooks/useFormDraft";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { ControlField } from "@/components/FieldErrors";
import { invalidProps, useFieldErrors } from "@/hooks/useFieldErrors";

export function ApplicationPage() {
  const { id = "" } = useParams();
  const app = useApplication(id);
  if (app.isPending) return <LoadingState label="Loading the application…" />;
  if (app.isError && isGone(app.error)) return <PrivateUnavailable what="application" list={{ to: "/applications", label: "Your applications" }} />;
  if (app.isError) return <div className="page"><ErrorState error={app.error} onRetry={() => void app.refetch()} /></div>;
  return <Detail key={app.data.id} a={app.data} />;
}

function Detail({ a }: { a: Application }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const done = (next: Application) => {
    qc.setQueryData(["me", "application", next.id], next);
    void qc.invalidateQueries({ queryKey: ["me", "applications"] });
    // Kits and reflections read the event live: after an edit or removal they're refetched, not
    // shown from the cache with the old date.
    void qc.invalidateQueries({ queryKey: ["me", "kit", next.id] });
    void qc.invalidateQueries({ queryKey: ["me", "reflection", next.id] });
    void qc.invalidateQueries({ queryKey: ["me", "schedule"] });
    void qc.invalidateQueries({ queryKey: ["me", "prep", next.id] }); // a reschedule changes what's proposed
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
          <DraftComposer role={a.role_title} employer={a.employer} events={a.events} />
        </div>
        <aside className="stack">
          <PrepareCard a={a} />
          <LinksCard a={a} onDone={done} />
          <Card className="stack-sm">
            <h2 className="section-title">Keep or remove</h2>
            <p className="subtle">Archiving hides it from your board; nothing is lost. Deleting removes it, its events and its history, and each event's interview kit and reflection. Your stories, notes and schedule entries stay.</p>
            <span className="row">
              <Button size="sm" onClick={async () => done(await api.archiveApplication(a.id, !a.archived))}>{a.archived ? "Unarchive" : "Archive"}</Button>
              <Button size="sm" variant="danger" onClick={async () => {
                if (!window.confirm(`Delete ${a.role_title} at ${a.employer}, its events and its history, and the interview kits and reflections for those events? Your stories, notes and schedule entries stay. This can't be undone. (Archive keeps it out of the way instead.)`)) return;
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
  const { pathname } = useLocation();
  const back = { from: pathname, fromLabel: "Back to the application" }; // no private text in history state
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
            <PrepPanel appId={a.id} eventId={e.id} />
            <span className="row">
              <Button size="sm" variant="ghost" onClick={() => setEditing(e)}>Edit</Button>
              <Link to={`/applications/${a.id}/events/${e.id}/kit`} state={back}>Interview-day kit</Link>
              <Link to={`/applications/${a.id}/events/${e.id}/reflection`} state={back}>Reflect on this interview</Link>
              <ScheduleLink kind="application_event" refId={e.id} title={`Prepare: ${e.title} (${a.employer})`} label="Schedule preparation time" />
              <Button size="sm" variant="ghost" onClick={async () => {
                if (window.confirm(`Remove “${e.title}”? Its interview kit and reflection are removed with it. Your stories, notes and schedule entries stay.`)) onDone(await api.deleteApplicationEvent(a.id, e.id));
              }}>Remove</Button>
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
  // A retry of the same event keeps its key (added once); an edited one before it's saved is new.
  const requestKey = useRequestKey();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const ambiguous = error instanceof ApiError && error.code === "ambiguous_time" ? (error.details as { first_offset: string; second_offset: string }) : null;
  const set = (k: keyof typeof form, v: string) => { setForm((f) => ({ ...f, [k]: v })); setFold(null); };
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const fields = {
      kind: form.kind, title: form.title, on_date: form.on_date || null, local_time: form.local_time || null,
      timezone: form.local_time ? form.timezone : null, notes: form.notes, fold,
    };
    const body = { ...fields, client_request_id: event ? null : requestKey.keyFor([a.id, fields]) };
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

/** The details a save can refuse field by field (the notes have their own conflict handling). */
const DETAIL_FIELDS = ["role_title", "employer", "link", "applied_on", "next_action", "next_action_due"] as const;

/** This browser's unsaved private notes for one application, with the revision they were edited
 * from (Volume 8, prompt 5). Kept per account: another account never reads them. */
const notesDraftKey = (userId: string, appId: string) => `codecoach.appnotes.v1.${userId}.${appId}`;
function readNotesDraft(key: string): { notes: string; base: number } | null {
  try {
    const raw = window.localStorage.getItem(key);
    const v = raw ? (JSON.parse(raw) as { notes?: unknown; base?: unknown }) : null;
    return v && typeof v.notes === "string" && typeof v.base === "number" ? { notes: v.notes, base: v.base } : null;
  } catch {
    return null;
  }
}

function DetailsCard({ a, onDone }: { a: Application; onDone: (a: Application) => void }) {
  const { user } = useAuth();
  const draftKey = notesDraftKey(user?.id ?? "anon", a.id);
  const [form, setForm] = useState({ role_title: a.role_title, employer: a.employer, link: a.link ?? "", applied_on: a.applied_on ?? "", next_action: a.next_action, next_action_due: a.next_action_due ?? "", notes: a.notes });
  // The form as it is now, for code that runs after a save's reply: `form` there is what it was
  // when Save was pressed, so "typed while saving" has to be read from here.
  const latest = useRef(form);
  useEffect(() => { latest.current = form; }, [form]);
  // A refused save's field errors, shown beside the fields while they still hold the refused
  // values (Volume 9, prompt 3).
  const errId = useCallback((k: string) => `app-${a.id}-${k}`, [a.id]);
  const fieldErrors = useFieldErrors(DETAIL_FIELDS, form, { ids: errId });
  const err = (k: (typeof DETAIL_FIELDS)[number]) => fieldErrors.errorFor(k);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // What the server last accepted: "Saved." only while the form still says exactly that, so a slow
  // response never labels newer edits as saved.
  const [savedAs, setSavedAs] = useState<string | null>(null);
  // The notes as the server has them, and their revision: a notes change is saved against it, and
  // a newer one elsewhere is compared, never overwritten (Volume 8, prompt 5).
  const [notesSaved, setNotesSaved] = useState({ text: a.notes, revision: a.notes_revision });
  const [conflict, setConflict] = useState<{ notes: string; revision: number } | null>(null);
  const [earlierSave, setEarlierSave] = useState<number | null>(null);
  const [recovered, setRecovered] = useState(() => {
    const d = readNotesDraft(draftKey);
    return d && d.notes !== a.notes ? d : null;
  });
  const [kept, setKept] = useState(true);
  const saveKey = useRequestKey();
  const notesDirty = form.notes !== notesSaved.text;
  // The other details, against what was loaded or last accepted (typing and putting it back isn't
  // a change). Either unsaved: leaving asks first (Volume 9, prompt 1).
  const fieldsOf = (f: typeof form) => JSON.stringify({ ...f, notes: undefined });
  const [acceptedFields, setAcceptedFields] = useState(() => fieldsOf(form));
  const fieldsDirty = fieldsOf(form) !== acceptedFields;
  useLeaveWarning(notesDirty || fieldsDirty, "this application's details");
  type Fields = Omit<typeof form, "notes">;
  const fieldsOnly = ({ notes: _notes, ...rest }: typeof form): Fields => rest;
  const fieldsDraft = useFormDraft<Fields>({
    storageKey: formDraftKey(user?.id ?? "anon", "application", a.id), form: fieldsOnly(form),
    baseline: JSON.parse(acceptedFields) as Fields, base: a.updated_at, enabled: Boolean(user),
    isForm: (v): v is Fields => isTextForm(v, ["role_title", "employer", "link", "applied_on", "next_action", "next_action_due"]),
  });
  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }));
  function setNotes(v: string) {
    set("notes", v);
    try {
      if (v !== notesSaved.text) window.localStorage.setItem(draftKey, JSON.stringify({ notes: v, base: notesSaved.revision }));
      else window.localStorage.removeItem(draftKey);
      setKept(true);
    } catch {
      setKept(v === notesSaved.text); // private mode or full: the text is on this page only
    }
  }
  function clearDraft() {
    try { window.localStorage.removeItem(draftKey); } catch { /* nothing kept */ }
  }

  async function submit(e?: FormEvent, over?: number) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    fieldErrors.clear();
    const sentForm = form;
    const sent = JSON.stringify(sentForm);
    const base = over ?? notesSaved.revision;
    const notesChanged = sentForm.notes !== notesSaved.text || over !== undefined;
    const clear = (["link", "applied_on", "next_action_due"] as const).filter((k) => !sentForm[k] && a[k]);
    try {
      const notes = notesChanged ? { notes: sentForm.notes, notes_expected_revision: base, client_request_id: saveKey.keyFor([a.id, base, sentForm.notes]) } : {};
      const next = await api.updateApplication(a.id, {
        role_title: sentForm.role_title, employer: sentForm.employer, next_action: sentForm.next_action,
        link: sentForm.link || null, applied_on: sentForm.applied_on || null, next_action_due: sentForm.next_action_due || null, clear, ...notes,
      });
      saveKey.done();
      const replay = recoveredSave(next);
      if (replay?.newer) {
        // Saved (its reply was lost), then changed elsewhere: compare, don't replace this page.
        setEarlierSave(replay.accepted);
        setConflict({ notes: next.notes, revision: next.notes_revision });
        onDone(next);
        return;
      }
      onDone(next);
      setAcceptedFields(fieldsOf(sentForm));
      fieldErrors.clear();
      fieldsDraft.accepted(fieldsOnly(sentForm), fieldsOnly(latest.current));
      setNotesSaved({ text: next.notes, revision: next.notes_revision });
      setConflict(null);
      setEarlierSave(null);
      setSavedAs(sent);
      if (latest.current.notes === sentForm.notes) clearDraft(); // typed while saving: that text stays kept
      setRecovered(null);
    } catch (err) {
      if (err instanceof ApiError && err.code === "notes_conflict") {
        const d = err.details as { current: string; current_revision: number };
        setEarlierSave(null);
        setConflict({ notes: d.current, revision: d.current_revision });
      } else if (fieldErrors.rejected(err, sentForm)) {
        // shown beside the fields it names
      } else {
        setError(err);
      }
    } finally {
      setBusy(false);
    }
  }

  function takeSaved(c: { notes: string; revision: number }) {
    setForm((f) => ({ ...f, notes: c.notes }));
    setNotesSaved({ text: c.notes, revision: c.revision });
    setConflict(null);
    setEarlierSave(null);
    clearDraft();
  }

  return (
    <form className="card stack-sm" aria-label="Details" onSubmit={(e) => void submit(e)}>
      <h2 className="section-title">Details</h2>
      <div className="app-form__grid">
        <ControlField id={errId("role_title")} label="Role title" error={err("role_title")}><input className="input" id={errId("role_title")} {...invalidProps(`${errId("role_title")}-error`, err("role_title"))} required maxLength={120} value={form.role_title} onChange={(e) => set("role_title", e.target.value)} /></ControlField>
        <ControlField id={errId("employer")} label="Employer" error={err("employer")}><input className="input" id={errId("employer")} {...invalidProps(`${errId("employer")}-error`, err("employer"))} required maxLength={120} value={form.employer} onChange={(e) => set("employer", e.target.value)} /></ControlField>
        <ControlField id={errId("applied_on")} label="Applied on" error={err("applied_on")}><input className="input" id={errId("applied_on")} {...invalidProps(`${errId("applied_on")}-error`, err("applied_on"))} type="date" value={form.applied_on} onChange={(e) => set("applied_on", e.target.value)} /></ControlField>
        <ControlField id={errId("link")} label="Link to the posting" error={err("link")}><input className="input" id={errId("link")} {...invalidProps(`${errId("link")}-error`, err("link"))} type="url" maxLength={500} value={form.link} onChange={(e) => set("link", e.target.value)} placeholder="https://" /></ControlField>
        <ControlField id={errId("next_action")} label="Next action" error={err("next_action")}><input className="input" id={errId("next_action")} {...invalidProps(`${errId("next_action")}-error`, err("next_action"))} maxLength={300} value={form.next_action} onChange={(e) => set("next_action", e.target.value)} /></ControlField>
        <ControlField id={errId("next_action_due")} label="Next action due" error={err("next_action_due")}><input className="input" id={errId("next_action_due")} {...invalidProps(`${errId("next_action_due")}-error`, err("next_action_due"))} type="date" value={form.next_action_due} onChange={(e) => set("next_action_due", e.target.value)} /></ControlField>
      </div>
      {a.link && <p className="subtle">Posting: {externalHref(a.link)
        ? <a href={externalHref(a.link)} target="_blank" rel="noopener noreferrer nofollow">{a.link}<span className="visually-hidden"> (opens in a new tab)</span></a>
        : <span>{a.link}</span>}</p>}
      {recovered && (
        <div className="banner banner--info stack-sm" role="region" aria-label="Unsaved notes found">
          <p>This browser has unsaved private notes for this application.</p>
          <span className="row">
            <Button size="sm" variant="primary" onClick={() => {
              set("notes", recovered.notes);
              // Edited from an older version than the one saved now: compare before saving over it.
              if (recovered.base !== notesSaved.revision) setConflict({ notes: notesSaved.text, revision: notesSaved.revision });
              setRecovered(null);
            }}>Restore them</Button>
            <Button size="sm" variant="ghost" onClick={() => { clearDraft(); setRecovered(null); }}>Discard them</Button>
          </span>
        </div>
      )}
      {conflict && (
        <VersionConflict what="private note" savedWhen={`version ${conflict.revision}`} busy={busy} earlierSave={earlierSave}
          keepMineLabel="Keep my notes (replaces that version)"
          fields={[{ label: "Private notes", mine: form.notes, saved: conflict.notes }]}
          onKeepMine={() => void submit(undefined, conflict.revision)}
          onUseSaved={() => takeSaved(conflict)} />
      )}
      <label className="field"><span className="field__label">Notes <span className="subtle">(private)</span></span><textarea className="input" rows={3} maxLength={4000} value={form.notes} onChange={(e) => setNotes(e.target.value)} /></label>
      {notesDirty && !kept && <p className="subtle">This browser can't keep a copy of unsaved notes: save them, or copy them somewhere safe.</p>}
      <InlineError error={error} />
      {fieldsDraft.offer && (
        <FormDraftOffer what="this application's details" at={fieldsDraft.offer.at} onDiscard={fieldsDraft.discard}
          newer={fieldsDraft.offer.base !== a.updated_at ? "This application was saved again after this copy was made. Restoring puts this copy in the form; saving it replaces those details." : null}
          onRestore={() => { const d = fieldsDraft.restore(); if (d) setForm((f) => ({ ...f, ...d.form })); }} />
      )}
      <FormDraftStatus changed={fieldsDirty} kept={fieldsDraft.kept} competing={fieldsDraft.competing}
        copyText={() => [form.role_title, form.employer, form.link, form.next_action].filter(Boolean).join("\n")} />
      {fieldErrors.other.length > 0 && <p className="field__error" role="alert">{fieldErrors.other.join(" ")}</p>}
      <span className="row"><Button type="submit" size="sm" variant="primary" loading={busy}>Save details</Button>{savedAs === JSON.stringify(form) && <span className="subtle" role="status">Saved.</span>}</span>
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
