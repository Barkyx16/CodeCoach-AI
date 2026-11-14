import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useStartInterview, useTarget, useTargetMutation } from "@/api/queries";
import type { Experience, Requirement, Target } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Icon } from "@/components/Icon";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { useAuth } from "@/auth/useAuth";
import { ErrorSummary, ControlField } from "@/components/FieldErrors";
import { FormDraftOffer, FormDraftStatus } from "@/components/FormDraftNotice";
import { invalidProps, useFieldErrors } from "@/hooks/useFieldErrors";
import { formDraftKey, isTextForm, useFormDraft } from "@/hooks/useFormDraft";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { formatDateTime } from "@/lib/format";
import { ActionLinks, RequirementHistory, RequirementSetEditor } from "@/features/targets/RequirementVersions";
import { useRequirementChange } from "@/features/targets/useRequirementChange";

type Category = Requirement["category"];
const GROUPS: { id: Category; label: string }[] = [
  { id: "required_skill", label: "Required skills" },
  { id: "responsibility", label: "Responsibilities" },
  { id: "experience", label: "Experience" },
  { id: "preferred_skill", label: "Preferred" },
  { id: "tool", label: "Tools and technologies" },
  { id: "competency", label: "Professional competencies" },
];
const ORIGIN: Record<Requirement["origin"], string> = {
  explicit: "From the posting",
  inferred: "Suggested (not in the posting)",
  user: "Added by you",
};
const COVERAGE_GLYPH: Record<Requirement["coverage"]["level"], string> = { practised: "●", some: "◑", limited: "○", gap: "✕" };

/** One target role: what it asks for, practice coverage per requirement, and what to do next. */
export function TargetWorkspace() {
  const { id = "" } = useParams();
  const target = useTarget(id);
  if (target.isPending) return <LoadingState label="Loading target role…" />;
  if (target.isError) {
    return <div className="page"><BackLink fallback={{ to: "/targets", label: "Target roles" }} /><ErrorState error={target.error} onRetry={() => void target.refetch()} /></div>;
  }
  return <Workspace t={target.data} />;
}

function Workspace({ t }: { t: Target }) {
  const update = useTargetMutation((body: Parameters<typeof api.updateTarget>[1]) => api.updateTarget(t.id, body));
  const [params, setParams] = useSearchParams();
  const [editingSet, setEditingSet] = useState(false);
  const view = params.get("show") ?? "all"; // all | gaps | limited | removed
  const shown = t.requirement_list.filter((r) =>
    view === "removed" ? r.removed
      : !r.removed && (view === "all" || (view === "gaps" ? r.coverage.level === "gap" : r.coverage.level === "limited" || r.coverage.level === "some")));
  const counts = {
    all: t.requirement_list.filter((r) => !r.removed).length,
    limited: t.requirement_list.filter((r) => !r.removed && (r.coverage.level === "limited" || r.coverage.level === "some")).length,
    gaps: t.requirement_list.filter((r) => !r.removed && r.coverage.level === "gap").length,
    removed: t.requirement_list.filter((r) => r.removed).length,
  };
  return (
    <div className="page target-workspace">
      <BackLink fallback={{ to: "/targets", label: "Target roles" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">PREPARE FOR THIS ROLE · {t.career_title.toUpperCase()}</p>
          <h1 className="page__title">{t.title}</h1>
          <p className="page__subtitle">
            {[t.employer, t.interview_date ? `Interview ${t.interview_date}${t.days_to_interview !== null && t.days_to_interview !== undefined ? ` (${t.days_to_interview} days)` : ""}` : null].filter(Boolean).join(" · ") || "No employer or date added"}
          </p>
        </div>
        <div className="row">
          {t.selected ? <Badge tone="success">Active target</Badge>
            : !t.archived && <Button variant="secondary" loading={update.isPending} onClick={() => update.mutate({ selected: true })}>Make active</Button>}
          <Button variant="ghost" loading={update.isPending} onClick={() => update.mutate({ archived: !t.archived })}>{t.archived ? "Unarchive" : "Archive"}</Button>
        </div>
      </div>
      <InlineError error={update.error} />

      <section className="stat-row" aria-label="Practice coverage summary">
        <Card className="stat"><span className="stat__label">Requirements</span><strong className="stat__value">{counts.all}</strong><span className="subtle">{t.requirement_list.filter((r) => !r.removed && r.origin === "explicit").length} from the posting</span></Card>
        <Card className="stat"><span className="stat__label">Practised</span><strong className="stat__value">{t.requirement_list.filter((r) => !r.removed && r.coverage.level === "practised").length}</strong><span className="subtle">2+ questions, average 70+</span></Card>
        <Card className="stat"><span className="stat__label">Need practice</span><strong className="stat__value">{counts.limited}</strong><span className="subtle">Limited or some evidence</span></Card>
        <Card className="stat"><span className="stat__label">Gaps</span><strong className="stat__value">{counts.gaps}</strong><span className="subtle">Not covered by the question bank</span></Card>
      </section>
      <p className="subtle">This is practice coverage from your own answers and code, not a chance of getting the job.</p>

      <div className="target-workspace__layout">
        <div className="stack">
          <Sessions t={t} />
          <section className="stack" aria-labelledby="req-title">
            <div className="section-heading">
              <h2 className="section-title" id="req-title">Requirements</h2>
              {!editingSet && <Button size="sm" variant="secondary" onClick={() => setEditingSet(true)}>Edit requirements</Button>}
            </div>
            {editingSet && <RequirementSetEditor t={t} groups={GROUPS} onDone={() => setEditingSet(false)} />}
            <div className="practice-switch" role="group" aria-label="Show requirements">
              {(["all", "limited", "gaps", "removed"] as const).map((v) => (
                <a key={v} href={`?show=${v}`} aria-current={view === v ? "page" : undefined}
                  onClick={(e) => { e.preventDefault(); setParams(v === "all" ? {} : { show: v }, { replace: true }); }}>
                  {{ all: "All", limited: "Need practice", gaps: "Gaps", removed: "Removed" }[v]} ({counts[v]})
                </a>
              ))}
            </div>
            {GROUPS.map((g) => {
              const items = shown.filter((r) => r.category === g.id && r.origin !== "inferred");
              return items.length > 0 && (
                <section key={g.id} className="stack" aria-labelledby={`group-${g.id}`}>
                  <h3 className="assessment__h" id={`group-${g.id}`}>{g.label}</h3>
                  {items.map((r) => <RequirementCard key={r.id} t={t} r={r} />)}
                </section>
              );
            })}
            {shown.some((r) => r.origin === "inferred") && (
              <section className="stack" aria-labelledby="group-inferred">
                <h3 className="assessment__h" id="group-inferred">Suggested for {t.career_title} roles (not in this posting)</h3>
                {shown.filter((r) => r.origin === "inferred").map((r) => <RequirementCard key={r.id} t={t} r={r} />)}
              </section>
            )}
            {shown.length === 0 && <p className="subtle">Nothing here.</p>}
            <AddRequirement t={t} />
          </section>
        </div>
        <aside className="stack">
          <Attempts t={t} />
          <ExperienceSection t={t} />
          <SourceSection t={t} />
        </aside>
      </div>
    </div>
  );
}

function Sessions({ t }: { t: Target }) {
  const start = useStartInterview();
  const navigate = useNavigate();
  const activeId = start.error instanceof ApiError && start.error.code === "interview_in_progress"
    ? (start.error.details as { interview_id?: string } | null)?.interview_id ?? null : null;
  async function run(round: NonNullable<Target["mock_interview"]["round"]>) {
    try {
      const iv = await start.mutateAsync({ kind: "questions", purpose: "practice", track: round.track, question_ids: round.question_ids ?? null, duration_minutes: round.duration_minutes });
      navigate(`/interviews/${iv.id}`);
    } catch { /* shown below */ }
  }
  return (
    <Card className="stack">
      <h2 className="section-title"><Icon name="target" size={16} />Next for this role</h2>
      {t.next_activity ? (
        <div className="continue-card__main">
          <div><strong>{t.next_activity.title}</strong><p className="subtle">{t.next_activity.why}</p></div>
          <Link className="btn btn--primary btn--md" to={t.next_activity.href} state={{ from: `/targets/${t.id}`, fromLabel: "Back to this role" }}>Practise this</Link>
        </div>
      ) : <p className="subtle">Every requirement the bank covers has practice. Try a mock interview for this role.</p>}
      <div className="target-sessions">
        {[t.targeted_session, t.mock_interview].map((s) => (
          <details key={s.title} className="target-session">
            <summary>{s.title}</summary>
            <p className="subtle">{s.scope}</p>
            {s.round && <Button variant="secondary" loading={start.isPending} onClick={() => void run(s.round!)}>Start ({s.round.question_ids?.length} questions, {s.round.duration_minutes} min)</Button>}
          </details>
        ))}
      </div>
      {activeId && <p className="banner banner--warning" role="alert">You already have an interview in progress. <Link to={`/interviews/${activeId}`}>Resume it</Link> first.</p>}
      {!activeId && <InlineError error={start.error} />}
    </Card>
  );
}

function RequirementCard({ t, r }: { t: Target; r: Requirement }) {
  const location = useLocation();
  const [editing, setEditing] = useState(false);
  const change = useRequirementChange(t, r, () => setEditing(false));
  const [text, setText] = useState(r.text);
  const [category, setCategory] = useState<Category>(r.category);
  return (
    <article className={`requirement requirement--${r.coverage.level}${r.removed ? " requirement--removed" : ""}`} aria-labelledby={`req-${r.id}`}>
      <div className="requirement__head">
        <h4 className="requirement__text" id={`req-${r.id}`}>{r.text}</h4>
        <span className={`coverage coverage--${r.coverage.level}`}><span aria-hidden="true">{COVERAGE_GLYPH[r.coverage.level]}</span> {r.coverage.label}</span>
      </div>
      <p className="subtle requirement__meta">
        {ORIGIN[r.origin]}{r.skills.length > 0 ? ` · Practises: ${r.skills.join(", ")}` : " · No matching skill in the question bank"}
      </p>
      <RequirementHistory t={t} r={r} />
      <ActionLinks t={t} r={r} />
      {r.quote && (
        <details className="requirement__source">
          <summary>Source text{r.quote_in_description ? "" : " (no longer in the description)"}</summary>
          <blockquote>{r.quote}</blockquote>
        </details>
      )}
      {!r.removed && r.practice.length > 0 && (
        <ul className="requirement__practice">
          {r.practice.map((p) => (
            <li key={p.href}>
              <Link to={p.href} state={{ from: location.pathname + location.search, fromLabel: "Back to this role" }}>{p.kind === "problem" ? "Problem: " : ""}{p.title}</Link>
              <span className="subtle"> · {p.why}{p.answered ? "" : ""}</span>
            </li>
          ))}
        </ul>
      )}
      {editing ? (
        <form className="stack requirement__edit" onSubmit={(e: FormEvent) => { e.preventDefault(); void change.propose({ text, category }); }}>
          <label className="field"><span className="field__label">Requirement</span>
            <input className="input" value={text} minLength={2} maxLength={300} onChange={(e) => setText(e.target.value)} /></label>
          <label className="field"><span className="field__label">Group</span>
            <select className="select" value={category} onChange={(e) => setCategory(e.target.value as Category)}>
              {GROUPS.map((g) => <option key={g.id} value={g.id}>{g.label}</option>)}
            </select></label>
          <div className="row"><Button type="submit" size="sm" variant="primary" loading={change.busy}>Save</Button><Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button></div>
        </form>
      ) : (
        <div className="row requirement__actions">
          {r.removed
            ? <Button size="sm" variant="ghost" loading={change.busy} onClick={() => void change.propose({ removed: false })}>Restore</Button>
            : <>
              <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>Correct</Button>
              <Button size="sm" variant="ghost" loading={change.busy} onClick={() => void change.propose({ removed: true })}>Remove</Button>
            </>}
        </div>
      )}
      {change.review}
      <InlineError error={change.error} />
    </article>
  );
}

function AddRequirement({ t }: { t: Target }) {
  const add = useTargetMutation((body: Parameters<typeof api.addRequirement>[1]) => api.addRequirement(t.id, body));
  const [text, setText] = useState("");
  const [category, setCategory] = useState<Category>("required_skill");
  return (
    <form className="add-requirement" aria-label="Add a requirement" onSubmit={(e) => { e.preventDefault(); add.mutate({ text, category }, { onSuccess: () => setText("") }); }}>
      <label className="field"><span className="field__label">Add a requirement the posting missed</span>
        <input className="input" value={text} maxLength={300} onChange={(e) => setText(e.target.value)} /></label>
      <label className="field"><span className="field__label">Group</span>
        <select className="select" value={category} onChange={(e) => setCategory(e.target.value as Category)}>
          {GROUPS.map((g) => <option key={g.id} value={g.id}>{g.label}</option>)}
        </select></label>
      <Button type="submit" variant="secondary" loading={add.isPending} disabled={text.trim().length < 2}>Add</Button>
      <InlineError error={add.error} />
    </form>
  );
}

function Attempts({ t }: { t: Target }) {
  const location = useLocation();
  return (
    <Card className="stack">
      <h2 className="section-title">Recent relevant attempts</h2>
      {t.recent_attempts.length === 0 ? <p className="subtle">None yet. Answers to questions linked to these requirements show up here with their feedback.</p> : (
        <ul className="rec-list">
          {t.recent_attempts.map((a) => (
            <li key={a.answer_id}>
              <Link className="rec" to={a.href} state={{ from: location.pathname + location.search, fromLabel: "Back to this role" }}>
                <strong>{a.question_title}</strong><span className="subtle">Scored {a.score}/100 · {formatDateTime(a.created_at)}{versionNote(t, a.requirement_versions)} · revisit feedback</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** When an attempt was answered against an earlier wording of a requirement it practises, say which. */
function versionNote(t: Target, versions: Record<string, number | null> | undefined): string {
  for (const [rid, v] of Object.entries(versions ?? {})) {
    const r = t.requirement_list.find((x) => x.id === rid);
    if (r && typeof v === "number" && v < r.version) return ` · answered against an earlier wording of “${r.text}” (version ${v}; now ${r.version})`;
  }
  return "";
}

function ReuseButton({ t, entryId, requirementId }: { t: Target; entryId: string; requirementId: string }) {
  const reuse = useTargetMutation(() => api.reuseStory(t.id, entryId, requirementId));
  return (
    <>
      <Button size="sm" variant="ghost" loading={reuse.isPending} onClick={() => reuse.mutate(undefined)}>Use it for the current wording</Button>
      <InlineError error={reuse.error} />
    </>
  );
}

const EMPTY = { title: "", situation: "", action: "", result: "", requirement_ids: [] as string[] };

function ExperienceSection({ t }: { t: Target }) {
  const [editing, setEditing] = useState<Experience | "new" | null>(null);
  return (
    <Card className="stack">
      <h2 className="section-title">Your examples</h2>
      <p className="subtle">Short notes on real things you've done, linked to the requirements they show. Written by you; nothing is added or rewritten for you. Each one is also in <Link to="/stories">your story bank</Link>, where you can add the task, a reflection and more.</p>
      {t.experience.map((e) => editing !== e && (
        <div key={e.id} className="experience">
          <strong>{e.title}</strong>
          {e.situation && <p><span className="activity-card__label">Situation:</span> {e.situation}</p>}
          {e.action && <p><span className="activity-card__label">What I did:</span> {e.action}</p>}
          {e.result && <p><span className="activity-card__label">Result:</span> {e.result}</p>}
          {(e.requirement_links ?? []).length === 0 ? <p className="subtle">Shows: no requirement linked</p> : (
            <ul className="mini-list">
              {(e.requirement_links ?? []).map((lk) => (
                <li key={lk.requirement_id}>
                  <span>Shows “{t.requirement_list.find((r) => r.id === lk.requirement_id)?.text}”</span>
                  <span className="subtle"> · {lk.label}</span>
                  {lk.status === "earlier_wording" && (
                    <> <ReuseButton t={t} entryId={e.id} requirementId={lk.requirement_id} /></>
                  )}
                </li>
              ))}
            </ul>
          )}
          <span className="row">
            <Button size="sm" variant="ghost" onClick={() => setEditing(e)}>Edit</Button>
            <Link to={`/stories/${e.id}`}>Open in your story bank</Link>
          </span>
        </div>
      ))}
      {editing ? <ExperienceForm key={editing === "new" ? "new" : editing.id} t={t} entry={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
        : <Button variant="secondary" onClick={() => setEditing("new")}>Add an example</Button>}
    </Card>
  );
}

function ExperienceForm({ t, entry, onDone }: { t: Target; entry: Experience | null; onDone: () => void }) {
  const [form, setForm] = useState(entry ? { title: entry.title, situation: entry.situation ?? "", action: entry.action ?? "", result: entry.result ?? "", requirement_ids: entry.requirement_ids ?? [] } : EMPTY);
  // An edit names the story revision it started from, so an older tab can't overwrite newer work (409).
  const save = useTargetMutation((body: typeof form) => entry ? api.editExperience(t.id, entry.id, { ...body, expected_revision: entry.revision }) : api.addExperience(t.id, body));
  const remove = useTargetMutation(() => api.deleteExperience(t.id, entry!.id));
  const field = (k: "title" | "situation" | "action" | "result", label: string, rows = 0) => (
    <label className="field"><span className="field__label">{label}</span>
      {rows ? <textarea className="input" rows={rows} maxLength={1500} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
        : <input className="input" maxLength={120} required value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />}
    </label>
  );
  return (
    <form className="stack" aria-label={entry ? "Edit example" : "New example"} onSubmit={(e) => { e.preventDefault(); save.mutate(form, { onSuccess: onDone }); }}>
      {field("title", "Short title")}
      {field("situation", "Situation (optional)", 2)}
      {field("action", "What you did (optional)", 2)}
      {field("result", "Result (optional)", 2)}
      <fieldset className="field">
        <legend className="field__label">Requirements it shows</legend>
        {t.requirement_list.filter((r) => !r.removed).map((r) => (
          <label key={r.id} className="checkbox">
            <input type="checkbox" checked={form.requirement_ids.includes(r.id)}
              onChange={() => setForm({ ...form, requirement_ids: form.requirement_ids.includes(r.id) ? form.requirement_ids.filter((x) => x !== r.id) : [...form.requirement_ids, r.id] })} />
            {r.text}
          </label>
        ))}
      </fieldset>
      <InlineError error={save.error ?? remove.error} />
      <div className="row">
        <Button type="submit" variant="primary" loading={save.isPending} disabled={!form.title.trim()}>Save example</Button>
        <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
        {entry && <Button type="button" variant="ghost" loading={remove.isPending} onClick={() => remove.mutate(undefined, { onSuccess: onDone })}>Delete</Button>}
      </div>
    </form>
  );
}

const POSTING_FIELDS = ["title", "employer", "interview_date", "notes", "description"] as const;
const POSTING_LABELS: Record<(typeof POSTING_FIELDS)[number], string> = {
  title: "Role title", employer: "Employer", interview_date: "Interview date", notes: "Notes", description: "Job description",
};

function SourceSection({ t }: { t: Target }) {
  const [editing, setEditing] = useState(false);
  const saved = { title: t.title, employer: t.employer ?? "", description: t.description, interview_date: t.interview_date ?? "", notes: t.notes ?? "" };
  const [form, setForm] = useState(saved);
  const update = useTargetMutation((body: Parameters<typeof api.updateTarget>[1]) => api.updateTarget(t.id, body));
  const again = useTargetMutation(() => api.reextract(t.id));
  // Unsaved: the open editor differs from the posting as saved (Volume 9, prompt 1).
  const current = useRef(form);
  useEffect(() => { current.current = form; }, [form]);
  const dirty = editing && JSON.stringify(form) !== JSON.stringify(saved);
  useLeaveWarning(dirty, "the job posting");
  const { user } = useAuth();
  const draft = useFormDraft<typeof saved>({
    storageKey: formDraftKey(user?.id ?? "anon", "posting", t.id), form: editing ? form : saved, baseline: saved, base: t.updated_at,
    isForm: (v): v is typeof saved => isTextForm(v, ["title", "employer", "description", "interview_date", "notes"]),
    enabled: Boolean(user),
  });
  const fid = useCallback((k: string) => `posting-${t.id}-${k}`, [t.id]);
  const fieldErrors = useFieldErrors(POSTING_FIELDS, form, { ids: fid, summaryId: fid("errors") });
  const err = (k: (typeof POSTING_FIELDS)[number]) => fieldErrors.errorFor(k);
  return (
    <Card className="stack">
      <h2 className="section-title">The posting</h2>
      {draft.offer && (
        <FormDraftOffer what="this posting" at={draft.offer.at} onDiscard={draft.discard}
          newer={draft.offer.base !== t.updated_at ? "The posting was saved again after this copy was made (in another tab or on another device). Restoring puts this copy in the editor; saving it replaces what's saved now." : null}
          onRestore={() => { const d = draft.restore(); if (d) { setForm(d.form); setEditing(true); } }} />
      )}
      {editing ? (
        <form className="stack" aria-label="Edit the posting" onSubmit={(e) => {
          e.preventDefault();
          fieldErrors.clear();
          const sent = JSON.stringify(form);
          const sentForm = form;
          // Closes only when nothing was typed while saving; otherwise the newer text stays open.
          update.mutate({ title: form.title, employer: form.employer || null, description: form.description, interview_date: form.interview_date || null, notes: form.notes || null },
            { onSuccess: () => {
              draft.accepted(JSON.parse(sent) as typeof saved, current.current);
              if (JSON.stringify(current.current) === sent) setEditing(false);
            },
            onError: (error) => { fieldErrors.rejected(error, sentForm); } });
        }}>
          <ErrorSummary id={fid("errors")} other={fieldErrors.other}
            items={fieldErrors.active.map(({ name, message }) => ({ fieldId: fid(name), label: POSTING_LABELS[name], message }))} />
          <ControlField id={fid("title")} label="Role title" error={err("title")}><input id={fid("title")} {...invalidProps(`${fid("title")}-error`, err("title"))} className="input" required maxLength={120} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></ControlField>
          <ControlField id={fid("employer")} label="Employer" error={err("employer")}><input id={fid("employer")} {...invalidProps(`${fid("employer")}-error`, err("employer"))} className="input" maxLength={120} value={form.employer} onChange={(e) => setForm({ ...form, employer: e.target.value })} /></ControlField>
          <ControlField id={fid("interview_date")} label="Interview date" error={err("interview_date")}><input id={fid("interview_date")} {...invalidProps(`${fid("interview_date")}-error`, err("interview_date"))} className="input" type="date" value={form.interview_date} onChange={(e) => setForm({ ...form, interview_date: e.target.value })} /></ControlField>
          <ControlField id={fid("notes")} label="Notes" error={err("notes")}><input id={fid("notes")} {...invalidProps(`${fid("notes")}-error`, err("notes"))} className="input" maxLength={2000} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></ControlField>
          <ControlField id={fid("description")} label="Job description" error={err("description")}><textarea id={fid("description")} {...invalidProps(`${fid("description")}-error`, err("description"))} className="input target-jd" rows={10} maxLength={20000} required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></ControlField>
          <p className="subtle">Saving keeps your requirements, edits and every attempt. Lines you remove are flagged on their requirement; use "Find requirements again" to add new ones.</p>
          {!fieldErrors.shown && <InlineError error={update.error} />}
          <FormDraftStatus changed={dirty} kept={draft.kept} competing={draft.competing} copyText={() => [form.title, form.employer, form.description, form.notes].filter(Boolean).join("\n\n")} />
          <div className="row"><Button type="submit" variant="primary" loading={update.isPending}>Save</Button><Button type="button" variant="ghost" onClick={() => { setForm(saved); setEditing(false); }}>Cancel</Button></div>
        </form>
      ) : (
        <>
          {t.notes && <p><span className="activity-card__label">Notes:</span> {t.notes}</p>}
          <details><summary>Show the description ({t.description.length.toLocaleString()} characters)</summary><pre className="target-jd-view">{t.description}</pre></details>
          <p className="subtle">Requirements found by: {t.extractor}.</p>
          <div className="row">
            <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>Edit</Button>
            <Button size="sm" variant="ghost" loading={again.isPending} onClick={() => again.mutate(undefined)}>Find requirements again</Button>
          </div>
          <InlineError error={again.error} />
        </>
      )}
    </Card>
  );
}
