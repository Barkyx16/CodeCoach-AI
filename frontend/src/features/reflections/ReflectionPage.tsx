import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useReflection, useStories } from "@/api/queries";
import type { Reflection, ReflectionAction, ReflectionIn, ReflectionOutcome } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { CopyWork } from "@/components/CopyWork";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { PrivateUnavailable } from "@/components/Unavailable";
import { isGone } from "@/lib/errors";
import { VersionConflict } from "@/components/VersionConflict";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { recoveredSave, savedVersion } from "@/lib/conflict";
import { useRequestKey } from "@/lib/requestKey";
import { formatDateTime, timeAgo } from "@/lib/format";

import { ListField } from "./ListField";
import { OUTCOME_LABEL, STAGE_FOR, STAGE_LABEL } from "./labels";

type Draft = Required<Omit<ReflectionIn, "expected_revision" | "client_request_id">>;

const fromReflection = (r: Reflection): Draft => ({
  questions: r.questions, topics: r.topics, clear: r.clear, difficult: r.difficult,
  observations: r.observations, follow_ups: r.follow_ups, practice: r.practice, story_ids: r.story_ids,
});

/** A private debrief of a real interview: the learner's own observations, then next steps they choose. */
export function ReflectionPage() {
  const { id = "", eventId = "" } = useParams();
  const reflection = useReflection(id, eventId);
  if (reflection.isPending) return <LoadingState label="Loading your reflection…" />;
  if (reflection.isError && isGone(reflection.error)) return <PrivateUnavailable what="reflection" list={{ to: "/reflections", label: "Your reflections" }} />;
  if (reflection.isError) return <div className="page"><ErrorState error={reflection.error} onRetry={() => void reflection.refetch()} /></div>;
  return <Editor key={eventId} initial={reflection.data} />;
}

const BACK_TO_REFLECTION = "Back to your reflection";

function Editor({ initial }: { initial: Reflection }) {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const qc = useQueryClient();
  const key = `reflection-draft:${user?.id ?? "anon"}:${initial.event_id}`;
  const [r, setR] = useState(initial);
  const [draft, setDraft] = useState<Draft>(() => fromReflection(initial));
  // A copy kept on this device, and the saved version it was written against (null: an older copy
  // that didn't record it). Restoring one written against an older version compares first.
  const [recovery, setRecovery] = useState<{ draft: Draft; base: number | null } | null>(() => {
    try {
      const raw = localStorage.getItem(key);
      const parsed = raw ? (JSON.parse(raw) as { draft?: Draft; base?: number } & Partial<Draft>) : null;
      const kept = parsed ? (parsed.draft ? { draft: parsed.draft, base: parsed.base ?? null } : { draft: parsed as Draft, base: null }) : null;
      return kept && JSON.stringify(kept.draft) !== JSON.stringify(fromReflection(initial)) ? kept : null;
    } catch {
      return null;
    }
  });
  // The version saved elsewhere, when a save was refused (409) or a kept copy is older than it.
  const [against, setAgainst] = useState<Reflection | null>(null);
  // One key per exact save: a retry after a lost reply is told "went through", not "changed elsewhere".
  const saveKey = useRequestKey();
  const [earlierSave, setEarlierSave] = useState<number | null>(null);
  const [keptHere, setKeptHere] = useState(true);
  // The draft as last rendered, for a save that resolves after newer edits.
  const latest = useRef(draft);
  useEffect(() => { latest.current = draft; }, [draft]);
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
    let ok = true;
    try {
      localStorage.setItem(key, JSON.stringify({ draft, base: r.revision }));
    } catch {
      ok = false; // private mode or full: the text exists only on this page now, and the page says so
    }
    queueMicrotask(() => setKeptHere(ok)); // storage answered: report it (not a render-time update)
  }, [draft, dirty, recovery, key, r.revision]);

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => {
    setStatus(""); // "Saved" was about the text before this edit
    setDraft((d) => ({ ...d, [k]: v }));
  };
  const put = (next: Reflection) => {
    setR(next);
    qc.setQueryData(["me", "reflection", next.application_id, next.event_id], next);
    void qc.invalidateQueries({ queryKey: ["me", "reflections"] });
    // An outcome can move the application's stage: its pages shouldn't show the old one.
    void qc.invalidateQueries({ queryKey: ["me", "application", next.application_id] });
    void qc.invalidateQueries({ queryKey: ["me", "applications"] });
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
    const sent = draft;
    setBusy("save");
    setError(null);
    try {
      const next = await api.saveReflection(r.application_id, r.event_id,
        { ...sent, expected_revision: revision, client_request_id: saveKey.keyFor([r.event_id, revision, sent]) });
      saveKey.done();
      const recovered = recoveredSave(next);
      if (recovered?.newer) {
        // Saved (the reply was lost), then changed elsewhere: compare, don't replace this page.
        setEarlierSave(recovered.accepted);
        setAgainst(next);
        return;
      }
      put(next);
      setAgainst(null);
      setEarlierSave(null);
      // Typed while it was saving? Those edits stay, unsaved; "Saved" is only for exactly what was sent.
      if (JSON.stringify(latest.current) === JSON.stringify(sent)) {
        setDraft(fromReflection(next));
        setStatus(recovered ? `Your earlier save went through (version ${recovered.accepted}). Only you can see it.` : "Saved. Only you can see it.");
        try { localStorage.removeItem(key); } catch { /* blocked */ }
      }
    } catch (err) {
      if (err instanceof ApiError && err.code === "stale_revision") {
        setEarlierSave(null);
        setAgainst(savedVersion<Reflection>(err.details) ?? (await api.reflection(r.application_id, r.event_id).catch(() => null)));
      } else {
        setError(err);
      }
    } finally {
      setBusy(null);
    }
  }

  function takeSaved(version: Reflection) {
    put(version);
    setDraft(fromReflection(version));
    setRestored((n) => n + 1);
    setAgainst(null);
    setEarlierSave(null);
    setStatus("Loaded the saved version.");
    try { localStorage.removeItem(key); } catch { /* blocked */ }
  }

  const lines = (xs: string[]) => xs.join("\n");
  const observed = (xs: Draft["observations"]) => xs.map((o) => `${o.kind === "observed" ? "Observed" : "My interpretation"}: ${o.text}`).join("\n");

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
      <p className="subtle">
        <Link to={`/applications/${r.application_id}/events/${r.event_id}/kit`} state={{ from: pathname, fromLabel: BACK_TO_REFLECTION }}>Your interview kit for this interview</Link>
      </p>

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
            <Button size="sm" variant="primary" onClick={() => {
              setDraft(recovery.draft);
              setRecovery(null);
              setRestored((n) => n + 1);
              // Kept against an older saved version: compare before anything is saved over it.
              if (recovery.base !== null && recovery.base !== r.revision) setAgainst(r);
            }}>Restore them</Button>
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
              <span key={s.id} className="row reflection-stories__item">
                <label className="checkbox">
                  <input type="checkbox" checked={draft.story_ids.includes(s.id)}
                    onChange={(e) => set("story_ids", e.target.checked ? [...draft.story_ids, s.id] : draft.story_ids.filter((x) => x !== s.id))} />
                  {s.title}
                </label>
                {/* Editing is the story's own, versioned flow: nothing here changes the story. */}
                {r.story_ids.includes(s.id) && (
                  <Link to={`/stories/${s.id}`} state={{ from: pathname, fromLabel: BACK_TO_REFLECTION }} aria-label={`Revise “${s.title}” in your story bank`}>Revise this story</Link>
                )}
              </span>
            ))}
          </fieldset>
        )}
        {r.missing_stories > 0 && (
          <p className="subtle" role="status">
            {r.missing_stories === 1 ? "A story you linked was" : `${r.missing_stories} stories you linked were`} deleted from your story bank since.
            Your reflection is unchanged; saving it removes the link.
          </p>
        )}
        <span className="row">
          <Button type="submit" variant="primary" loading={busy === "save"} disabled={!dirty}>Save reflection</Button>
          <span className="subtle" role="status">{status || (dirty ? (keptHere ? "Unsaved changes, kept on this device" : "Unsaved changes, and this browser can't keep a copy: save, or copy your text") : r.saved ? `Saved ${r.updated_at ? formatDateTime(r.updated_at) : ""}` : "")}</span>
          {dirty && !keptHere && <CopyWork text={[draft.clear, draft.difficult, observed(draft.observations), draft.follow_ups].filter(Boolean).join("\n\n")} />}
        </span>
        {r.warnings.map((w) => <p key={w} className="banner banner--warning">{w}</p>)}
        {against && (
          <VersionConflict what="reflection" savedWhen={`version ${against.revision}${against.updated_at ? `, ${timeAgo(against.updated_at)}` : ""}`}
            busy={busy === "save"} keepMineLabel="Keep mine as the newest" earlierSave={earlierSave}
            fields={[
              { label: "Questions you were asked", mine: lines(draft.questions), saved: lines(against.questions) },
              { label: "Topics that came up", mine: lines(draft.topics), saved: lines(against.topics) },
              { label: "What felt clear", mine: draft.clear, saved: against.clear },
              { label: "What was difficult", mine: draft.difficult, saved: against.difficult },
              { label: "Observations", mine: observed(draft.observations), saved: observed(against.observations) },
              { label: "What you said you'd do", mine: draft.follow_ups, saved: against.follow_ups },
              { label: "What you want to practise", mine: lines(draft.practice), saved: lines(against.practice) },
            ]}
            onKeepMine={() => void save(undefined, against.revision)}
            onUseSaved={() => takeSaved(against)} />
        )}
        <InlineError error={error} />
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
  const { pathname } = useLocation();
  const back = { from: pathname, fromLabel: BACK_TO_REFLECTION };
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
        {a.href ? <Link to={a.href} state={back}>{a.title}</Link> : <strong>{a.title}</strong>}
      </div>
      {a.detail && <p className="subtle">{a.detail}</p>}
      {a.status === "accepted" ? (
        a.applied_available === false ? (
          <p className="reflection-action__done">
            You added this to {a.target ? where[a.target] : "your account"}, and {a.target === "notebook" ? "deleted that note" : a.target === "schedule" ? "removed it from your schedule" : "removed it from Saved"} since.
            It isn't added again from here{a.target === "notebook" ? " (a deleted note can be restored from your notebook for a short time)" : ""}.
          </p>
        ) : (
          <p className="reflection-action__done">Added to {a.target ? where[a.target] : "your account"}.{a.target === "notebook" && a.applied_ref && <> <Link to={`/notes/${a.applied_ref}`} state={back}>Open the note</Link></>}{a.target === "schedule" && <> <Link to="/schedule">Open your schedule</Link></>}{a.target === "saved" && <> <Link to="/saved">Open Saved</Link></>}</p>
        )
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
  const [result, setResult] = useState("");
  const stage = STAGE_FOR[outcome];
  async function submit() {
    const before = r.outcome_history.length;
    const next = await run("outcome", () => api.setReflectionOutcome(r.application_id, r.event_id, { outcome, update_application: apply && !!stage }));
    if (!next) return; // the error is shown; nothing was saved (the outcome and the stage are saved together)
    const last = next.outcome_history.at(-1);
    if (next.outcome_history.length === before) setResult("Nothing changed: that outcome was already recorded.");
    else if (last?.applied_to_application && stage) setResult(`Outcome saved, and the application moved to “${STAGE_LABEL[stage]}”.`);
    else if (apply && stage) setResult(`Outcome saved. The application was already at “${STAGE_LABEL[stage]}”, so it wasn't moved.`);
    else setResult("Outcome saved. The application wasn't changed.");
    setApply(false);
  }
  return (
    <section className="card stack-sm" aria-labelledby="outcome-title">
      <h2 className="section-title" id="outcome-title">What happened next</h2>
      <p className="subtle">Only what you've been told. A slow reply isn't a rejection, and nothing here is used to score your practice.</p>
      <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
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
        {result && <p className="subtle" role="status">{result}</p>}
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
