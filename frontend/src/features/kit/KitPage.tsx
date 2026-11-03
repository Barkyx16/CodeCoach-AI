import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useKit, useStories } from "@/api/queries";
import type { Kit, KitQuestion } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { describeWhen } from "@/features/applications/dates";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { useMediaQuery } from "@/hooks/useMediaQuery";

import { DEFAULT_PRINT, FORMAT_LABEL, GROUP_LABEL, PRINT_LABEL, type KitFormat, type PrintChoice, type QuestionGroup } from "./labels";
import { PrintPack } from "./PrintPack";

const newId = () => `u-${crypto.randomUUID().slice(0, 8)}`;

/** The interview-day kit for one recorded interview event. */
export function KitPage() {
  const { id = "", eventId = "" } = useParams();
  const kit = useKit(id, eventId);
  if (kit.isPending) return <LoadingState label="Loading your interview kit…" />;
  if (kit.isError) return <div className="page"><ErrorState error={kit.error} onRetry={() => void kit.refetch()} /></div>;
  return <KitEditor key={`${kit.data.event_id}`} initial={kit.data} />;
}

function KitEditor({ initial }: { initial: Kit }) {
  const qc = useQueryClient();
  const narrow = useMediaQuery("(max-width: 640px)");
  const stories = useStories({});
  const [saved, setSaved] = useState(initial);
  const [kit, setKit] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState("");
  const [print, setPrint] = useState<PrintChoice>(DEFAULT_PRINT);
  const dirty = JSON.stringify(kit) !== JSON.stringify(saved);
  useLeaveWarning(dirty);
  const set = <K extends keyof Kit>(k: K, v: Kit[K]) => { setKit((x) => ({ ...x, [k]: v })); setNotice(""); };

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const next = await api.saveKit(kit.application_id, kit.event_id, {
        format: kit.format, location: kit.location, meeting_link: kit.meeting_link || null, clear_meeting_link: !kit.meeting_link,
        interviewers: kit.interviewers, notes: kit.notes, checklist: kit.checklist, questions: kit.questions, story_ids: kit.stories.map((s) => s.id),
      });
      setSaved(next);
      setKit(next);
      qc.setQueryData(["me", "kit", kit.application_id, kit.event_id], next);
      setNotice("Saved.");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const remaining = kit.checklist.filter((c) => !c.done && !c.hidden);
  const asking = kit.questions.filter((q) => !q.excluded);
  const move = (i: number, by: -1 | 1) => {
    const qs = [...kit.questions];
    const [q] = qs.splice(i, 1);
    qs.splice(i + by, 0, q!);
    set("questions", qs);
  };
  const updateQ = (i: number, patch: Partial<KitQuestion>) => set("questions", kit.questions.map((q, j) => (j === i ? { ...q, ...patch } : q)));

  return (
    <div className="page kit-page">
      <div className="no-print">
        <BackLink fallback={{ to: `/applications/${kit.application_id}`, label: "Back to the application" }} />
      </div>
      <div className="page__header no-print">
        <div>
          <p className="eyebrow">INTERVIEW DAY</p>
          <h1 className="page__title">{kit.event_title}</h1>
          <p className="page__subtitle">{kit.role_title} at {kit.employer} · {describeWhen(kit)}</p>
        </div>
      </div>

      <section className="card stack-sm before-view no-print" aria-labelledby="before-title">
        <h2 className="section-title" id="before-title">Before the interview</h2>
        <p><strong>{describeWhen(kit)}</strong> · {FORMAT_LABEL[kit.format]}{kit.format === "in_person" && kit.location ? ` · ${kit.location}` : ""}</p>
        {kit.meeting_link && (
          <details open={!narrow}>
            <summary>Meeting link</summary>
            <p><a href={kit.meeting_link} target="_blank" rel="noopener noreferrer nofollow">{kit.meeting_link}<span className="visually-hidden"> (opens in a new tab)</span></a></p>
          </details>
        )}
        <div className="before-view__grid">
          <div>
            <h3 className="section-title">Examples to bring</h3>
            {kit.stories.length === 0 ? <p className="subtle">None chosen yet.</p> : <ul className="mini-list">{kit.stories.map((s) => <li key={s.id}><Link to={`/stories/${s.id}`}>{s.title}</Link>{s.short_version && <span className="subtle"> · {s.short_version}</span>}</li>)}</ul>}
          </div>
          <div>
            <h3 className="section-title">Questions you'll ask</h3>
            {asking.length === 0 ? <p className="subtle">None chosen.</p> : <ol className="mini-list">{asking.map((q) => <li key={q.id}>{q.text}</li>)}</ol>}
          </div>
          <div>
            <h3 className="section-title">Still to do</h3>
            {remaining.length === 0 ? <p className="subtle">Nothing left on your list.</p> : <ul className="mini-list">{remaining.map((c) => <li key={c.id}>{c.text}</li>)}</ul>}
          </div>
        </div>
        {kit.format === "remote" && <p className="subtle">Want to check your microphone? The <Link to="/interviews">mock interview setup</Link> has a microphone test (it isn't recorded).</p>}
        <p className="subtle">Read your examples once more, and take your time with each question. This page is for you; nothing on it is sent anywhere.</p>
      </section>

      <div className="kit-page__layout no-print">
        <div className="stack">
          <Card className="stack-sm">
            <h2 className="section-title">Logistics</h2>
            <div className="app-form__grid">
              <label className="field"><span className="field__label">Format</span>
                <select className="select" value={kit.format} onChange={(e) => set("format", e.target.value as KitFormat)}>
                  {(Object.keys(FORMAT_LABEL) as KitFormat[]).map((f) => <option key={f} value={f}>{FORMAT_LABEL[f]}</option>)}
                </select>
              </label>
              <label className="field"><span className="field__label">Location <span className="subtle">(optional)</span></span><input className="input" maxLength={500} value={kit.location} onChange={(e) => set("location", e.target.value)} /></label>
              <label className="field"><span className="field__label">Meeting link <span className="subtle">(optional, private)</span></span><input className="input" type="url" maxLength={500} placeholder="https://" value={kit.meeting_link ?? ""} onChange={(e) => set("meeting_link", e.target.value || null)} /></label>
            </div>
            <p className="subtle">CodeCoach never opens or checks the link; it's kept for you, and left out of exports to other pages and of the printout unless you choose it.</p>
            <fieldset className="stack-sm">
              <legend className="field__label">Interviewers <span className="subtle">(optional; as you know them)</span></legend>
              {kit.interviewers.map((p, i) => (
                <div key={i} className="row kit-interviewer">
                  <label className="field"><span className="field__label">Name</span><input className="input" maxLength={80} value={p.name} onChange={(e) => set("interviewers", kit.interviewers.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} /></label>
                  <label className="field"><span className="field__label">Role</span><input className="input" maxLength={80} value={p.role} onChange={(e) => set("interviewers", kit.interviewers.map((x, j) => (j === i ? { ...x, role: e.target.value } : x)))} /></label>
                  <Button size="sm" variant="ghost" onClick={() => set("interviewers", kit.interviewers.filter((_, j) => j !== i))}>Remove</Button>
                </div>
              ))}
              {kit.interviewers.length < 10 && <span><Button size="sm" onClick={() => set("interviewers", [...kit.interviewers, { name: "", role: "" }])}>Add an interviewer</Button></span>}
            </fieldset>
          </Card>

          <Card className="stack-sm">
            <h2 className="section-title">Checklist</h2>
            <p className="subtle">Ticking an item means you've done it. CodeCoach doesn't check your camera, connection, documents or travel.</p>
            <ul className="kit-checklist">
              {kit.checklist.map((c, i) => (
                <li key={c.id} className={c.hidden ? "kit-checklist__hidden" : undefined}>
                  {c.hidden ? (
                    <span className="subtle">Hidden: {c.text} <Button size="sm" variant="ghost" onClick={() => set("checklist", kit.checklist.map((x, j) => (j === i ? { ...x, hidden: false } : x)))}>Restore</Button></span>
                  ) : (
                    <>
                      <label className="checkbox"><input type="checkbox" checked={c.done} onChange={(e) => set("checklist", kit.checklist.map((x, j) => (j === i ? { ...x, done: e.target.checked } : x)))} />{c.text}</label>
                      <Badge>{c.origin === "suggested" ? "Suggested" : "Yours"}</Badge>
                      <Button size="sm" variant="ghost" aria-label={`Hide “${c.text}”`} onClick={() => set("checklist", kit.checklist.map((x, j) => (j === i ? { ...x, hidden: true } : x)))}>Hide</Button>
                    </>
                  )}
                </li>
              ))}
            </ul>
            <AddLine label="Add a checklist item" onAdd={(text) => set("checklist", [...kit.checklist, { id: newId(), text, origin: "yours", done: false, hidden: false }])} max={200} />
          </Card>

          <Card className="stack-sm">
            <h2 className="section-title">Questions to ask them</h2>
            <p className="subtle">In order of priority. Suggestions come from your job target and common topics; they never assume anything about the employer.</p>
            <ol className="kit-questions">
              {kit.questions.map((q, i) => (
                <li key={q.id} className={q.excluded ? "kit-questions__excluded" : undefined}>
                  <label className="field"><span className="visually-hidden">Question {i + 1}</span>
                    <input className="input" maxLength={300} value={q.text} onChange={(e) => updateQ(i, { text: e.target.value })} />
                  </label>
                  <span className="row">
                    <Badge>{GROUP_LABEL[q.group as QuestionGroup]}</Badge>
                    <Badge tone={q.origin === "suggested" ? "neutral" : "info"}>{q.origin === "suggested" ? "Suggested" : "Yours"}</Badge>
                    <Button size="sm" variant="ghost" disabled={i === 0} aria-label={`Move “${q.text}” up`} onClick={() => move(i, -1)}>Up</Button>
                    <Button size="sm" variant="ghost" disabled={i === kit.questions.length - 1} aria-label={`Move “${q.text}” down`} onClick={() => move(i, 1)}>Down</Button>
                    <label className="checkbox"><input type="checkbox" checked={!q.excluded} onChange={(e) => updateQ(i, { excluded: !e.target.checked })} />Ask this</label>
                  </span>
                  {q.note && <p className="subtle">{q.note}</p>}
                </li>
              ))}
            </ol>
            <AddLine label="Add your own question" onAdd={(text) => set("questions", [...kit.questions, { id: newId(), text, group: "other", origin: "yours", excluded: false, note: null }])} max={300} />
          </Card>

          <Card className="stack-sm">
            <h2 className="section-title">Examples to bring</h2>
            {(stories.data ?? []).length === 0 ? <p className="subtle">No stories yet. <Link to="/stories/new">Write one</Link>.</p> : (
              <fieldset className="stack-sm">
                <legend className="visually-hidden">Stories</legend>
                {(stories.data ?? []).map((s) => (
                  <label key={s.id} className="checkbox">
                    <input type="checkbox" checked={kit.stories.some((x) => x.id === s.id)}
                      onChange={(e) => set("stories", e.target.checked ? [...kit.stories, { id: s.id, title: s.title, short_version: "" }] : kit.stories.filter((x) => x.id !== s.id))} />
                    {s.title}
                  </label>
                ))}
              </fieldset>
            )}
          </Card>

          <details className="card stack-sm" open={!narrow}>
            <summary className="section-title">Private notes</summary>
            <label className="field"><span className="visually-hidden">Private notes</span>
              <textarea className="input" rows={4} maxLength={4000} value={kit.notes} onChange={(e) => set("notes", e.target.value)} />
            </label>
          </details>

          <div className="kit-save">
            <Button variant="primary" loading={busy} disabled={!dirty} onClick={() => void save()}>Save kit</Button>
            <span className="subtle" role="status">{notice || (dirty ? "Unsaved changes" : kit.saved ? "All changes saved" : "These are suggestions; save to keep your changes")}</span>
            <InlineError error={error} />
          </div>
        </div>

        <aside className="stack">
          <Card className="stack-sm">
            <h2 className="section-title">Print or save as PDF</h2>
            <p className="subtle">Choose what goes in. The preview below is exactly what prints; use your browser's “Save as PDF” in the print dialog for a file. Nothing is sent to the employer.</p>
            <fieldset className="stack-sm">
              <legend className="visually-hidden">Include</legend>
              {(Object.keys(PRINT_LABEL) as (keyof PrintChoice)[]).map((k) => (
                <label key={k} className="checkbox"><input type="checkbox" checked={print[k]} onChange={(e) => setPrint({ ...print, [k]: e.target.checked })} />{PRINT_LABEL[k]}</label>
              ))}
            </fieldset>
            <span><Button size="sm" onClick={() => window.print()} disabled={dirty}>Print…</Button></span>
            {dirty && <p className="subtle">Save your changes first, so the printout matches what's saved.</p>}
          </Card>
        </aside>
      </div>
      <section className="kit-preview" aria-label="Print preview">
        <p className="eyebrow no-print">PRINT PREVIEW</p>
        <PrintPack kit={kit} choice={print} />
      </section>
    </div>
  );
}

function AddLine({ label, onAdd, max }: { label: string; onAdd: (text: string) => void; max: number }) {
  const [text, setText] = useState("");
  return (
    <form className="row" onSubmit={(e) => { e.preventDefault(); if (text.trim()) { onAdd(text.trim()); setText(""); } }}>
      <label className="field"><span className="field__label">{label}</span><input className="input" maxLength={max} value={text} onChange={(e) => setText(e.target.value)} /></label>
      <Button type="submit" size="sm" disabled={!text.trim()}>Add</Button>
    </form>
  );
}
