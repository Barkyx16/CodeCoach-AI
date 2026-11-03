import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useReflection, useStories } from "@/api/queries";
import type { Reflection, ReflectionAction, ReflectionIn, ReflectionOutcome } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { formatDateTime } from "@/lib/format";

import { ListField } from "./ListField";
import { OUTCOME_LABEL, STAGE_FOR, STAGE_LABEL } from "./labels";

type Draft = Required<Omit<ReflectionIn, "expected_revision">>;

const fromReflection = (r: Reflection): Draft => ({
  questions: r.questions, topics: r.topics, clear: r.clear, difficult: r.difficult,
  observations: r.observations, follow_ups: r.follow_ups, practice: r.practice, story_ids: r.story_ids,
});

/** A private debrief of a real interview: the learner's own observations, then next steps they choose. */
export function ReflectionPage() {
  const { id = "", eventId = "" } = useParams();
  const reflection = useReflection(id, eventId);
  if (reflection.isPending) return <LoadingState label="Loading your reflection…" />;
  if (reflection.isError) return <div className="page"><ErrorState error={reflection.error} onRetry={() => void reflection.refetch()} /></div>;
  return <Editor key={eventId} initial={reflection.data} />;
}

function Editor({ initial }: { initial: Reflection }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const key = `reflection-draft:${user?.id ?? "anon"}:${initial.event_id}`;
  const [r, setR] = useState(initial);
  const [draft, setDraft] = useState<Draft>(() => fromReflection(initial));
  const [recovery, setRecovery] = useState<Draft | null>(() => {
    try {
      const raw = localStorage.getItem(key);
      const kept = raw ? (JSON.parse(raw) as Draft) : null;
      return kept && JSON.stringify(kept) !== JSON.stringify(fromReflection(initial)) ? kept : null;
    } catch {
      return null;
    }
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [status, setStatus] = useState("");
  const [restored, setRestored] = useState(0); // remounts the line lists after a restore
  const stories = useStories({}, true);
  const dirty = JSON.stringify(draft) !== JSON.stringify(fromReflection(r));
  useLeaveWarning(dirty);
  // Unsaved words are kept on this device until saved, so a failed save or a closed tab loses nothing.
  useEffect(() => {
    if (!dirty || recovery) return;
    try { localStorage.setItem(key, JSON.stringify(draft)); } catch { /* blocked: the leave warning still applies */ }
  }, [draft, dirty, recovery, key]);

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const put = (next: Reflection) => {
    setR(next);
    qc.setQueryData(["me", "reflection", next.application_id, next.event_id], next);
    void qc.invalidateQueries({ queryKey: ["me", "reflections"] });
  };

  async function run(label: string, fn: () => Promise<Reflection>, done?: string) {
    setBusy(label);
    setError(null);
    try {
      const next = await fn();
      put(next);
      if (done) setStatus(done);
      return next;
    } catch (e) {
      setError(e);
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function save(e?: FormEvent, revision = r.revision) {
    e?.preventDefault();
    const next = await run("save", () => api.saveReflection(r.application_id, r.event_id, { ...draft, expected_revision: revision }), "Saved. Only you can see it.");
    if (next) {
      setDraft(fromReflection(next));
      try { localStorage.removeItem(key); } catch { /* blocked */ }
    }
  }

  const conflict = error instanceof ApiError && error.code === "stale_revision" ? (error.details as { current_revision: number }).current_revision : null;

  return (
    <div className="page reflection-page">
      <BackLink fallback={{ to: `/applications/${r.application_id}`, label: `${r.role_title} at ${r.employer}` }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">AFTER THE INTERVIEW · PRIVATE</p>
          <h1 className="page__title">Reflect on {r.event_title}</h1>
          <p className="page__subtitle">
            {r.role_title} at {r.employer}{r.event_on ? ` · ${r.event_on}` : ""}. Your own notes about a real interview: not practice, and not AI feedback.
            Everything is optional, and unknown is fine.
          </p>
        </div>
      </div>
      {r.application_archived && <p className="banner banner--info">This application is archived. Your reflection stays here.</p>}

      <Card className="stack-sm reflection-guidance">
        <h2 className="section-title">Before you write</h2>
        <ul className="mini-list">
          <li>Paraphrase questions instead of copying them, and leave out test content you agreed not to share and anything secret to the employer.</li>
          <li>Leave out details that identify patients, clients, colleagues or interviewers.</li>
          <li>Audio isn't part of this. Don't record an interview without everyone's consent.</li>
          <li>Nothing here is sent to an AI model or to anyone else.</li>
        </ul>
      </Card>

      {recovery && (
        <div className="banner banner--info row" role="region" aria-label="Unsaved changes">
          <span>You have unsaved changes to this reflection on this device.</span>
          <span className="row">
            <Button size="sm" variant="primary" onClick={() => { setDraft(recovery); setRecovery(null); setRestored((n) => n + 1); }}>Restore them</Button>
            <Button size="sm" variant="ghost" onClick={() => { try { localStorage.removeItem(key); } catch { /* blocked */ } setRecovery(null); }}>Discard them</Button>
          </span>
        </div>
      )}

      <form className="card stack" onSubmit={(e) => void save(e)} aria-labelledby="reflection-form-title">
        <h2 className="section-title" id="reflection-form-title">What happened</h2>
        <ListField label="Questions you were asked" hint="In your own words. One per line." max={30} maxLength={300} value={draft.questions} onChange={(v) => set("questions", v)} key={`questions-${restored}`} />
        <ListField label="Topics that came up" hint="Short phrases, like “medication safety” or “handover”." max={20} maxLength={80} value={draft.topics} onChange={(v) => set("topics", v)} key={`topics-${restored}`} />
        <label className="field"><span className="field__label">What felt clear</span>
          <textarea className="input" rows={2} maxLength={3000} value={draft.clear} onChange={(e) => set("clear", e.target.value)} />
        </label>
        <label className="field"><span className="field__label">What was difficult</span>
          <textarea className="input" rows={2} maxLength={3000} value={draft.difficult} onChange={(e) => set("difficult", e.target.value)} />
        </label>
        <Observations value={draft.observations} onChange={(v) => set("observations", v)} />
        <label className="field"><span className="field__label">What you said you'd do</span>
          <span className="subtle">Follow-up commitments, like sending references. CodeCoach never sends anything for you.</span>
          <textarea className="input" rows={2} maxLength={2000} value={draft.follow_ups} onChange={(e) => set("follow_ups", e.target.value)} />
        </label>
        <ListField label="What you want to practise" hint="One per line." max={20} maxLength={300} value={draft.practice} onChange={(v) => set("practice", v)} key={`practice-${restored}`} />
        {(stories.data?.length ?? 0) > 0 && (
          <fieldset className="stack-sm reflection-stories">
            <legend className="field__label">Stories you used</legend>
            {stories.data!.map((s) => (
              <label key={s.id} className="checkbox">
                <input type="checkbox" checked={draft.story_ids.includes(s.id)}
                  onChange={(e) => set("story_ids", e.target.checked ? [...draft.story_ids, s.id] : draft.story_ids.filter((x) => x !== s.id))} />
                {s.title}
              </label>
            ))}
          </fieldset>
        )}
        <span className="row">
          <Button type="submit" variant="primary" loading={busy === "save"} disabled={!dirty}>Save reflection</Button>
          <span className="subtle" role="status">{status || (dirty ? "Unsaved changes, kept on this device" : r.saved ? `Saved ${r.updated_at ? formatDateTime(r.updated_at) : ""}` : "")}</span>
        </span>
        {r.warnings.map((w) => <p key={w} className="banner banner--warning">{w}</p>)}
        {conflict !== null && (
          <div className="banner banner--warning row" role="alert">
            <span>This reflection was saved somewhere else (now version {conflict}). Your text is still here.</span>
            <Button size="sm" variant="primary" onClick={() => void save(undefined, conflict)}>Save mine as the newest</Button>
          </div>
        )}
        {conflict === null && <InlineError error={error} />}
      </form>

      {r.saved && <NextSteps r={r} busy={busy} run={run} />}
      {r.saved && <OutcomeSection r={r} busy={busy} run={run} />}
      <p className="subtle"><Link to="/reflections">All your reflections</Link></p>
    </div>
  );
}

type Run = (label: string, fn: () => Promise<Reflection>, done?: string) => Promise<Reflection | null>;

function Observations({ value, onChange }: { value: Draft["observations"]; onChange: (v: Draft["observations"]) => void }) {
  const [text, setText] = useState("");
  const [kind, setKind] = useState<"observed" | "interpretation">("observed");
  return (
    <fieldset className="stack-sm reflection-observations">
      <legend className="field__label">Observations</legend>
      <p className="subtle">Keep what happened apart from what you think it meant. “They asked for another example” is something that happened; “they didn't like me” is a guess. Nothing is ever suggested from a guess.</p>
      <ul className="mini-list">
        {value.map((o, i) => (
          <li key={`${o.text}-${i}`} className="row">
            <Badge tone={o.kind === "observed" ? "info" : "neutral"}>{o.kind === "observed" ? "What happened" : "What I think it meant"}</Badge>
            <span>{o.text}</span>
            <Button size="sm" variant="ghost" aria-label={`Remove “${o.text}”`} onClick={() => onChange(value.filter((_, j) => j !== i))}>Remove</Button>
          </li>
        ))}
      </ul>
      <div className="row reflection-observations__add">
        <label className="field"><span className="field__label">Add an observation</span>
          <input className="input" maxLength={500} value={text} onChange={(e) => setText(e.target.value)} />
        </label>
        <span className="row" role="radiogroup" aria-label="Kind of observation">
          <label className="checkbox"><input type="radio" name="obs-kind" checked={kind === "observed"} onChange={() => setKind("observed")} />What happened</label>
          <label className="checkbox"><input type="radio" name="obs-kind" checked={kind === "interpretation"} onChange={() => setKind("interpretation")} />What I think it meant</label>
        </span>
        <Button size="sm" disabled={!text.trim() || value.length >= 30} onClick={() => { onChange([...value, { text: text.trim(), kind }]); setText(""); }}>Add observation</Button>
      </div>
    </fieldset>
  );
}

function NextSteps({ r, busy, run }: { r: Reflection; busy: string | null; run: Run }) {
  const open = r.actions.filter((a) => a.status !== "dismissed");
  const dismissed = r.actions.filter((a) => a.status === "dismissed");
  return (
    <section className="card stack" aria-labelledby="next-steps-title">
      <h2 className="section-title" id="next-steps-title">Next steps</h2>
      <p className="subtle">Suggested only from what you wrote and from practice that exists here. Nothing is added until you choose where it goes.</p>
      <span><Button loading={busy === "suggest"} onClick={() => void run("suggest", () => api.suggestReflectionSteps(r.application_id, r.event_id))}>{r.actions.length ? "Suggest again from my reflection" : "Suggest next steps"}</Button></span>
      {open.length > 0 && <ul className="reflection-actions">{open.map((a) => <ActionRow key={a.id} r={r} a={a} busy={busy} run={run} />)}</ul>}
      {dismissed.length > 0 && (
        <details>
          <summary>Dismissed ({dismissed.length})</summary>
          <ul className="reflection-actions">{dismissed.map((a) => <ActionRow key={a.id} r={r} a={a} busy={busy} run={run} />)}</ul>
        </details>
      )}
    </section>
  );
}

function ActionRow({ r, a, busy, run }: { r: Reflection; a: ReflectionAction; busy: string | null; run: Run }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(a.title);
  const [detail, setDetail] = useState(a.detail);
  const [date, setDate] = useState("");
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const where = { notebook: "your notebook", schedule: "your schedule", saved: "Saved" } as const;
  const base = [r.application_id, r.event_id] as const;
  return (
    <li className={`reflection-action reflection-action--${a.kind}`}>
      <div className="row">
        <Badge tone={a.kind === "gap" ? "warning" : a.kind === "practice" ? "info" : "neutral"}>{a.kind === "gap" ? "Gap" : a.kind === "practice" ? "Practice" : "Note"}</Badge>
        {a.href ? <Link to={a.href}>{a.title}</Link> : <strong>{a.title}</strong>}
      </div>
      {a.detail && <p className="subtle">{a.detail}</p>}
      {a.status === "accepted" ? (
        <p className="reflection-action__done">Added to {a.target ? where[a.target] : "your account"}.{a.target === "notebook" && a.applied_ref && <> <Link to={`/notes/${a.applied_ref}`}>Open the note</Link></>}</p>
      ) : editing ? (
        <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); void run(`edit-${a.id}`, () => api.editReflectionStep(...base, a.id, { title, detail })).then((n) => n && setEditing(false)); }}>
          <label className="field"><span className="field__label">Step</span><input className="input" maxLength={300} value={title} onChange={(e) => setTitle(e.target.value)} /></label>
          <label className="field"><span className="field__label">Details</span><textarea className="input" rows={2} maxLength={2000} value={detail} onChange={(e) => setDetail(e.target.value)} /></label>
          <span className="row"><Button type="submit" size="sm" variant="primary" loading={busy === `edit-${a.id}`}>Save</Button><Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button></span>
        </form>
      ) : a.status === "dismissed" ? (
        <span><Button size="sm" variant="ghost" onClick={() => void run(`restore-${a.id}`, () => api.editReflectionStep(...base, a.id, { status: "suggested" }))}>Bring back</Button></span>
      ) : (
        <div className="row reflection-action__buttons">
          {a.targets.includes("notebook") && <Button size="sm" loading={busy === `notebook-${a.id}`} onClick={() => void run(`notebook-${a.id}`, () => api.acceptReflectionStep(...base, a.id, { target: "notebook" }), "Added to your notebook.")}>Add to notebook</Button>}
          {a.targets.includes("saved") && <Button size="sm" loading={busy === `saved-${a.id}`} onClick={() => void run(`saved-${a.id}`, () => api.acceptReflectionStep(...base, a.id, { target: "saved" }), "Added to Saved.")}>Add to Saved</Button>}
          {a.targets.includes("schedule") && (
            <span className="row">
              <label className="field reflection-action__date"><span className="field__label">Date for “{a.title}”</span>
                <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
              </label>
              <Button size="sm" disabled={!date} loading={busy === `schedule-${a.id}`} onClick={() => void run(`schedule-${a.id}`, () => api.acceptReflectionStep(...base, a.id, { target: "schedule", on_date: date, timezone: tz }), "Added to your schedule.")}>Add to schedule</Button>
            </span>
          )}
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>Edit</Button>
          <Button size="sm" variant="ghost" onClick={() => void run(`dismiss-${a.id}`, () => api.editReflectionStep(...base, a.id, { status: "dismissed" }))}>Dismiss</Button>
        </div>
      )}
    </li>
  );
}

function OutcomeSection({ r, busy, run }: { r: Reflection; busy: string | null; run: Run }) {
  const [outcome, setOutcome] = useState<ReflectionOutcome>(r.outcome);
  const [apply, setApply] = useState(false);
  const stage = STAGE_FOR[outcome];
  return (
    <section className="card stack-sm" aria-labelledby="outcome-title">
      <h2 className="section-title" id="outcome-title">What happened next</h2>
      <p className="subtle">Only what you've been told. A slow reply isn't a rejection, and nothing here is used to score your practice.</p>
      <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); void run("outcome", () => api.setReflectionOutcome(r.application_id, r.event_id, { outcome, update_application: apply && !!stage }), "Outcome saved."); }}>
        <label className="field"><span className="field__label">Outcome</span>
          <select className="select" value={outcome} onChange={(e) => { setOutcome(e.target.value as ReflectionOutcome); setApply(false); }}>
            {(Object.keys(OUTCOME_LABEL) as ReflectionOutcome[]).map((o) => <option key={o} value={o}>{OUTCOME_LABEL[o]}</option>)}
          </select>
        </label>
        {stage && (
          <label className="checkbox"><input type="checkbox" checked={apply} onChange={(e) => setApply(e.target.checked)} />
            Also move the application to “{STAGE_LABEL[stage]}”
          </label>
        )}
        <span><Button type="submit" size="sm" loading={busy === "outcome"} disabled={outcome === r.outcome && !apply}>Save outcome</Button></span>
      </form>
      {r.outcome_history.length > 0 && (
        <ul className="mini-list subtle">
          {r.outcome_history.map((h) => (
            <li key={h.at}>{formatDateTime(h.at)}: {OUTCOME_LABEL[h.outcome]}{h.applied_to_application ? " (the application was updated)" : ""}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
