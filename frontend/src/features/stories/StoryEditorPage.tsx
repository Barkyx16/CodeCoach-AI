import { useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useStory, useTargets } from "@/api/queries";
import type { Competency, Story, StoryContext, StorySection } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { CareerSelect } from "@/features/careers/CareerSelect";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { formatDateTime } from "@/lib/format";

import { COMPETENCIES, COMPETENCY_LABEL, CONTEXT_LABEL, SECTION_LABEL, SECTION_PROMPT, SECTIONS } from "./labels";
import { RevisionsPanel } from "./RevisionsPanel";
import { changes, emptyForm, fromStory, sameForm, storyDraftKey, toBody, type StoryForm } from "./storyForm";
import { WritingHelp } from "./WritingHelp";

interface Recovery {
  form: StoryForm;
  base: number | null;
  at: string;
}

function readRecovery(key: string): Recovery | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Recovery) : null;
  } catch {
    return null;
  }
}

/** New story (/stories/new) or an existing one (/stories/:id). */
export function StoryEditorPage() {
  const { id } = useParams();
  const story = useStory(id);
  if (id && story.isPending) return <LoadingState label="Loading the story…" />;
  if (id && story.isError) return <div className="page"><ErrorState error={story.error} onRetry={() => void story.refetch()} /></div>;
  return <Editor key={id ?? "new"} story={id ? story.data! : null} />;
}

function Editor({ story }: { story: Story | null }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const targets = useTargets();
  const formId = useId();
  const key = storyDraftKey(user?.id ?? "anon", story?.id ?? "new");
  const [saved, setSaved] = useState<Story | null>(story);
  const base = saved ? fromStory(saved) : emptyForm(user?.career_track ?? "");
  const [form, setForm] = useState<StoryForm>(base);
  const [recovery, setRecovery] = useState<Recovery | null>(() => {
    const r = readRecovery(key);
    return r && !sameForm(r.form, base) ? r : null;
  });
  const [kept, setKept] = useState(true);
  const [assisted, setAssisted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [conflict, setConflict] = useState<number | null>(null);
  const [notice, setNotice] = useState("");
  const dirty = !sameForm(form, base);
  useLeaveWarning(dirty && !kept);

  // Every change is kept on this device until it's saved, so a closed tab loses nothing.
  function keep(next: StoryForm) {
    if (recovery) return; // don't overwrite a copy the learner hasn't decided about yet
    const changed = !sameForm(next, base);
    try {
      if (changed) window.localStorage.setItem(key, JSON.stringify({ form: next, base: saved?.revision ?? null, at: new Date().toISOString() }));
      else window.localStorage.removeItem(key);
      setKept(true);
    } catch {
      setKept(!changed);
    }
  }
  const edit = (next: StoryForm) => {
    setForm(next);
    keep(next);
  };
  const set = <K extends keyof StoryForm>(k: K, v: StoryForm[K]) => edit({ ...form, [k]: v });

  async function save(e?: FormEvent, overrideRevision?: number) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      let next: Story;
      if (!saved) {
        next = await api.createStory(toBody(form));
        window.localStorage.removeItem(key);
        qc.setQueryData(["me", "story", next.id], next);
        void qc.invalidateQueries({ queryKey: ["me", "stories"] });
        navigate(`/stories/${next.id}`, { replace: true });
        return;
      }
      next = await api.updateStory(saved.id, { clear_target: false, ...changes(base, form), expected_revision: overrideRevision ?? saved.revision, reason: assisted ? "assisted" : "edited" });
      setSaved(next);
      setForm(fromStory(next));
      setAssisted(false);
      setConflict(null);
      setNotice(next.revision === saved.revision ? "Nothing changed." : `Saved as version ${next.revision}.`);
      qc.setQueryData(["me", "story", next.id], next);
      void qc.invalidateQueries({ queryKey: ["me", "stories"] });
      void qc.invalidateQueries({ queryKey: ["me", "story", next.id, "revisions"] });
    } catch (err) {
      if (err instanceof ApiError && err.code === "stale_revision") {
        setConflict((err.details as { current_revision?: number } | null)?.current_revision ?? null);
      } else {
        setError(err);
      }
    } finally {
      setBusy(false);
    }
  }

  async function reloadSaved() {
    if (!saved) return;
    const fresh = await api.story(saved.id);
    setSaved(fresh);
    setForm(fromStory(fresh));
    setConflict(null);
  }

  function replaceWith(next: Story) {
    setSaved(next);
    setForm(fromStory(next));
    qc.setQueryData(["me", "story", next.id], next);
    void qc.invalidateQueries({ queryKey: ["me", "stories"] });
  }

  async function archive(archived: boolean) {
    if (!saved) return;
    replaceWith(await api.archiveStory(saved.id, archived));
    setNotice(archived ? "Archived. It's hidden from your list until you unarchive it." : "Back in your list.");
  }

  async function remove() {
    if (!saved || !window.confirm("Delete this story and every saved version of it? Answers you practised with it are kept. Interview kits and reflections that used it will say an example was deleted. This can't be undone.")) return;
    await api.deleteStory(saved.id);
    window.localStorage.removeItem(key);
    void qc.invalidateQueries({ queryKey: ["me", "stories"] });
    navigate("/stories", { replace: true });
  }

  const sections = { situation: form.situation, task: form.task, action: form.action, result: form.result, reflection: form.reflection };
  const missing = SECTIONS.filter((s) => s !== "reflection" && !sections[s].trim());

  return (
    <div className="page story-editor">
      <BackLink fallback={{ to: "/stories", label: "Your stories" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">STORY BANK{saved ? ` · VERSION ${saved.revision}` : ""}{saved?.archived ? " · ARCHIVED" : ""}</p>
          <h1 className="page__title">{saved ? saved.title : "Write a story"}</h1>
          <p className="page__subtitle">Describe something you really did, in your own words. Private to you.</p>
        </div>
      </div>

      {recovery && (
        <div className="banner banner--info row" role="region" aria-label="Unsaved changes">
          <span>You have unsaved changes to this story from {formatDateTime(recovery.at)} on this device.</span>
          <span className="row">
            <Button size="sm" variant="primary" onClick={() => { setForm(recovery.form); setRecovery(null); }}>Restore them</Button>
            <Button size="sm" variant="ghost" onClick={() => { window.localStorage.removeItem(key); setRecovery(null); }}>Discard them</Button>
          </span>
        </div>
      )}
      {conflict !== null && (
        <div className="banner banner--warning stack-sm" role="alert">
          <span>This story was saved somewhere else since you opened it (now version {conflict}). Your edits are still here and weren't saved.</span>
          <span className="row">
            <Button size="sm" variant="primary" loading={busy} onClick={() => void save(undefined, conflict)}>Save mine as the newest version</Button>
            <Button size="sm" variant="ghost" onClick={() => void reloadSaved()}>Discard mine and load the saved version</Button>
          </span>
        </div>
      )}

      <div className="story-editor__layout">
        <form id={formId} className="stack" onSubmit={(e) => void save(e)}>
          <Card className="stack-sm">
            <p className="subtle story-editor__privacy">
              Leave out names and details that identify patients, clients, customers or colleagues.
              “A patient”, “a client” or “my manager” works just as well.
            </p>
            {saved && saved.privacy_hints.length > 0 && (
              <div className="banner banner--warning" role="status">
                <strong>Worth a second look:</strong>
                <ul className="mini-list">{saved.privacy_hints.map((h) => <li key={h}>{h}</li>)}</ul>
              </div>
            )}
            <label className="field"><span className="field__label">Title</span>
              <input className="input" required maxLength={120} value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="For example: Two call lights at once" />
            </label>
            <div className="story-editor__row">
              <CareerSelect value={form.track} onChange={(v) => set("track", v)} label="Career this story is for" />
              <label className="field"><span className="field__label">Where it happened</span>
                <select className="select" value={form.context} onChange={(e) => set("context", e.target.value as StoryContext | "")}>
                  <option value="">Not set</option>
                  {(Object.keys(CONTEXT_LABEL) as StoryContext[]).map((c) => <option key={c} value={c}>{CONTEXT_LABEL[c]}</option>)}
                </select>
              </label>
            </div>
          </Card>

          <Card className="stack-sm">
            <h2 className="section-title">The story</h2>
            {missing.length > 0 && <p className="subtle">Not written yet: {missing.map((m) => SECTION_LABEL[m]).join(", ")}. You can save it unfinished.</p>}
            {SECTIONS.map((s) => <SectionField key={s} section={s} value={sections[s]} onChange={(v) => set(s, v)} />)}
          </Card>

          <Card className="stack-sm">
            <fieldset className="stack-sm">
              <legend className="section-title">What it shows</legend>
              <p className="subtle">One story can show several things.</p>
              <div className="story-editor__competencies">
                {COMPETENCIES.map((c) => (
                  <label key={c} className="checkbox">
                    <input type="checkbox" checked={form.competencies.includes(c)}
                      onChange={(e) => set("competencies", e.target.checked ? [...form.competencies, c] : form.competencies.filter((x: Competency) => x !== c))} />
                    {COMPETENCY_LABEL[c]}
                  </label>
                ))}
              </div>
            </fieldset>
            <label className="field"><span className="field__label">Skill tags <span className="subtle">(comma-separated, optional)</span></span>
              <input className="input" value={form.tags} onChange={(e) => set("tags", e.target.value)} placeholder="night shift, triage" />
            </label>
          </Card>

          <Card className="stack-sm">
            <h2 className="section-title">Supporting detail <span className="subtle">(optional, private)</span></h2>
            <label className="field"><span className="field__label">Notes</span>
              <textarea className="input" rows={3} maxLength={4000} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
            </label>
            <label className="field"><span className="field__label">Evidence of the outcome</span>
              <textarea className="input" rows={2} maxLength={2000} value={form.evidence} onChange={(e) => set("evidence", e.target.value)}
                placeholder="Something that shows the result, if you have it: feedback you received, a before-and-after" />
            </label>
          </Card>

          <Card className="stack-sm">
            <h2 className="section-title">Rehearsal versions <span className="subtle">(optional)</span></h2>
            <p className="subtle">Your own words for practising out loud. They're rehearsals, not scripts to memorise, and nothing guarantees how an interview goes.</p>
            <label className="field"><span className="field__label">Short version (about a minute)</span>
              <textarea className="input" rows={3} maxLength={3000} value={form.short_version} onChange={(e) => set("short_version", e.target.value)} />
            </label>
            <label className="field"><span className="field__label">Longer version (two or three minutes)</span>
              <textarea className="input" rows={5} maxLength={3000} value={form.long_version} onChange={(e) => set("long_version", e.target.value)} />
            </label>
          </Card>

          <Card className="stack-sm">
            <h2 className="section-title">Linked to</h2>
            <label className="field"><span className="field__label">Job target</span>
              <select className="select" value={form.target_id} onChange={(e) => set("target_id", e.target.value)}>
                <option value="">None</option>
                {(targets.data ?? []).filter((t) => !t.archived || t.id === form.target_id).map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
              </select>
            </label>
            {saved && saved.questions.length > 0 && (
              <ul className="mini-list">
                {saved.questions.map((q) => <li key={q.ref}><Link to={q.href}>{q.title}</Link>{!q.available && <span className="subtle"> (retired)</span>}</li>)}
              </ul>
            )}
            <p className="subtle">To practise this story, open a question and choose “Practise with one of your stories”.</p>
          </Card>

          <div className="story-editor__actions">
            <Button type="submit" variant="primary" loading={busy} disabled={!form.title.trim() || (!!saved && !dirty)}>{saved ? "Save changes" : "Save story"}</Button>
            <span className="subtle" role="status">{notice || (dirty ? (kept ? "Unsaved changes, kept on this device" : "Unsaved changes, and this browser can't keep a copy") : saved ? "All changes saved" : "")}</span>
          </div>
          <InlineError error={error} />
        </form>

        <aside className="stack">
          {saved
            ? <WritingHelp storyId={saved.id} sections={sections} onAccept={(field: StorySection, text: string) => { set(field, text); setAssisted(true); }} />
            : <Card className="stack-sm"><h2 className="section-title">Writing check</h2><p className="subtle">Save the story first, then you can check it for missing parts and wordiness.</p></Card>}
          {saved && saved.practice.length > 0 && (
            <Card className="stack-sm">
              <h2 className="section-title">Practised with this story</h2>
              <ul className="mini-list">
                {saved.practice.map((p) => <li key={p.answer_id}><Link to={p.href}>{p.question_title}</Link> <span className="subtle">· {p.too_short ? "too short to score" : `${p.score}/100`} · {formatDateTime(p.created_at)}</span></li>)}
              </ul>
              <p className="subtle">Each practice is its own answer; the story isn't changed by it.</p>
            </Card>
          )}
          {saved && <RevisionsPanel story={saved} onRestored={replaceWith} />}
          {saved && (
            <Card className="stack-sm">
              <h2 className="section-title">Keep or remove</h2>
              <span className="row">
                <Button size="sm" onClick={() => void archive(!saved.archived)}>{saved.archived ? "Unarchive" : "Archive"}</Button>
                <Button size="sm" variant="danger" onClick={() => void remove()}>Delete…</Button>
              </span>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}

function SectionField({ section, value, onChange }: { section: StorySection; value: string; onChange: (v: string) => void }) {
  const id = useId();
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>{SECTION_LABEL[section]}</label>
      <p className="subtle" id={`${id}-hint`}>{SECTION_PROMPT[section]}</p>
      <textarea id={id} className="input" rows={section === "action" ? 5 : 3} maxLength={4000} value={value}
        aria-describedby={`${id}-hint`} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
