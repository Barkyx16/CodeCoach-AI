import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { invalidateActionViews, useActions, useKit, useStories } from "@/api/queries";
import type { AcceptedAction, Kit, KitQuestion } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { PrivateUnavailable } from "@/components/Unavailable";
import { isGone } from "@/lib/errors";
import { VersionConflict } from "@/components/VersionConflict";
import { describeWhen } from "@/features/applications/dates";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { useMediaQuery } from "@/hooks/useMediaQuery";

import { DEFAULT_PRINT, FORMAT_LABEL, GROUP_LABEL, PRINT_LABEL, type KitFormat, type PrintChoice, type QuestionGroup } from "./labels";
import { KitTemplatesCard } from "./KitTemplatesCard";
import { PrintPack } from "./PrintPack";
import { recoveredSave, savedVersion } from "@/lib/conflict";
import { externalHref } from "@/lib/links";
import { useRequestKey } from "@/lib/requestKey";

const newId = () => `u-${crypto.randomUUID().slice(0, 8)}`;

/** The interview-day kit for one recorded interview event. */
export function KitPage() {
  const { id = "", eventId = "" } = useParams();
  const kit = useKit(id, eventId);
  if (kit.isPending) return <LoadingState label="Loading your interview kit…" />;
  if (kit.isError && isGone(kit.error)) return <PrivateUnavailable what="interview kit" list={{ to: "/applications", label: "Your applications" }} />;
  if (kit.isError) return <div className="page"><ErrorState error={kit.error} onRetry={() => void kit.refetch()} /></div>;
  // The editor keeps the learner's edits; the event's logistics (read live by the server) come from
  // the latest fetch, so a reschedule made elsewhere shows here without losing unsaved edits.
  return <KitEditor key={`${kit.data.event_id}`} initial={kit.data} live={kit.data} />;
}

const BACK_TO_KIT = "Back to the interview kit";

function KitEditor({ initial, live }: { initial: Kit; live: Kit }) {
  const qc = useQueryClient();
  const { pathname } = useLocation();
  const narrow = useMediaQuery("(max-width: 640px)");
  const stories = useStories({});
  const [saved, setSaved] = useState(initial);
  const [kit, setKit] = useState(initial);
  const [reviewed, setReviewed] = useState<string[]>([]);
  // A refused stale save: the kit saved elsewhere, shown beside this page's.
  const [conflict, setConflict] = useState<Kit | null>(null);
  // One key per exact save: a retry after a lost reply is told "went through", not "changed elsewhere".
  const saveKey = useRequestKey();
  const [earlierSave, setEarlierSave] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState("");
  const [print, setPrint] = useState<PrintChoice>(DEFAULT_PRINT);
  const dirty = JSON.stringify(kit) !== JSON.stringify(saved) || reviewed.length > 0;
  // The kit as last rendered, for a save that resolves after newer edits (it must not undo them).
  const latest = useRef(kit);
  useEffect(() => { latest.current = kit; }, [kit]);
  useLeaveWarning(dirty);
  const set = <K extends keyof Kit>(k: K, v: Kit[K]) => { setKit((x) => ({ ...x, [k]: v })); setNotice(""); };
  const fromHere = { from: pathname, fromLabel: BACK_TO_KIT };

  /** Saves against the revision this page loaded; `over` is an explicit "save mine over it". */
  async function save(over?: number) {
    setBusy(true);
    setError(null);
    const sent = kit;
    try {
      const update = {
        format: sent.format, location: sent.location, meeting_link: sent.meeting_link || null, clear_meeting_link: !sent.meeting_link,
        interviewers: sent.interviewers, notes: sent.notes, checklist: sent.checklist, questions: sent.questions, story_ids: sent.stories.map((s) => s.id),
        expected_revision: over ?? saved.revision, reviewed_story_ids: reviewed,
      };
      const next = await api.saveKit(sent.application_id, sent.event_id, { ...update, client_request_id: saveKey.keyFor([sent.event_id, update]) });
      saveKey.done();
      const recovered = recoveredSave(next);
      if (recovered?.newer) {
        // Saved (the reply was lost), then changed elsewhere: compare, don't replace this page.
        setEarlierSave(recovered.accepted);
        setConflict(next);
        return;
      }
      setEarlierSave(null);
      if (JSON.stringify(latest.current) === JSON.stringify(sent)) {
        replaceWith(next);
        setNotice(recovered ? `Your earlier save went through (version ${recovered.accepted}).` : "Saved.");
      } else {
        // Edited while it was saving: keep those edits, now unsaved against the version just saved.
        setSaved(next);
        setReviewed([]);
        setConflict(null);
        qc.setQueryData(["me", "kit", next.application_id, next.event_id], next);
      }
    } catch (e) {
      if (e instanceof ApiError && e.code === "stale_revision") {
        setEarlierSave(null);
        setConflict(savedVersion<Kit>(e.details) ?? (await api.kit(kit.application_id, kit.event_id).catch(() => null)));
      } else {
        setError(e);
      }
    } finally {
      setBusy(false);
    }
  }

  function replaceWith(next: Kit) {
    setSaved(next);
    setKit(next);
    setReviewed([]);
    setConflict(null);
    setEarlierSave(null);
    qc.setQueryData(["me", "kit", next.application_id, next.event_id], next);
  }

  // An accepted improvement on the checklist is the action itself (docs/ACCEPTED_ACTIONS.md): ticking it
  // says the action is done everywhere, at once, not as part of this kit's save.
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  async function toggleAction(actionId: string, done: boolean) {
    setActionBusy(actionId);
    setActionError(null);
    try {
      const a = await api.setActionDone(actionId, done);
      const patch = (k: Kit): Kit => ({ ...k, checklist: k.checklist.map((x) => (x.action_id === a.id ? { ...x, ...actionItem(a), id: x.id, hidden: x.hidden } : x)) });
      setKit(patch);
      setSaved(patch);
      invalidateActionViews(qc);
    } catch (e) {
      setActionError(e);
    } finally {
      setActionBusy(null);
    }
  }

  const people = (k: Kit) => k.interviewers.map((i) => [i.name, i.role].filter(Boolean).join(", ")).join("\n");
  const ticks = (k: Kit) => k.checklist.filter((c) => !c.hidden).map((c) => `${c.done ? "[x]" : "[ ]"} ${c.text}`).join("\n");
  const asks = (k: Kit) => k.questions.filter((q) => !q.excluded).map((q) => q.text).join("\n");

  // Chosen examples: the bank's own list, plus any chosen one that's archived (so it can be unticked).
  const pickable = [
    ...(stories.data ?? []).map((s) => ({ id: s.id, title: s.title, archived: false })),
    ...kit.stories.filter((s) => s.archived && !(stories.data ?? []).some((x) => x.id === s.id)).map((s) => ({ id: s.id, title: s.title, archived: true })),
  ];
  const changed = kit.stories.filter((s) => s.chosen_revision != null && s.revision > s.chosen_revision);

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
          <h1 className="page__title">{live.event_title}</h1>
          <p className="page__subtitle">{live.role_title} at {live.employer} · {describeWhen(live)}</p>
        </div>
      </div>

      {conflict && (
        <div className="no-print">
          <VersionConflict what="kit" savedWhen={`version ${conflict.revision}`} busy={busy} earlierSave={earlierSave} keepMineLabel="Keep mine (replaces that version)"
            fields={[
              { label: "Format", mine: FORMAT_LABEL[kit.format as KitFormat] ?? kit.format, saved: FORMAT_LABEL[conflict.format as KitFormat] ?? conflict.format },
              { label: "Where", mine: [kit.location, kit.meeting_link].filter(Boolean).join("\n"), saved: [conflict.location, conflict.meeting_link].filter(Boolean).join("\n") },
              { label: "Interviewers", mine: people(kit), saved: people(conflict) },
              { label: "Notes", mine: kit.notes, saved: conflict.notes },
              { label: "Checklist", mine: ticks(kit), saved: ticks(conflict) },
              { label: "Questions to ask", mine: asks(kit), saved: asks(conflict) },
              { label: "Examples", mine: kit.stories.map((x) => x.title).join("\n"), saved: conflict.stories.map((x) => x.title).join("\n") },
            ]}
            onKeepMine={() => void save(conflict.revision)}
            onUseSaved={() => { replaceWith(conflict); setNotice("Loaded the saved kit. Your unsaved changes were discarded."); }} />
        </div>
      )}
      {!conflict && live.revision > saved.revision && (
        <div className="banner banner--info no-print" role="status">
          This kit was saved somewhere else (maybe another tab) since you opened it.
          {dirty ? " Your changes here are kept; saving will ask before replacing that version." : " "}
          {!dirty && <Button size="sm" variant="ghost" onClick={() => replaceWith(live)}>Show the saved kit</Button>}
        </div>
      )}
      {live.rescheduled_from && (
        <div className="banner banner--info no-print" role="status">
          This interview moved since you last saved the kit: it was {describeWhen(live.rescheduled_from)}, and is now {describeWhen(live)}.
          Check the logistics, and anything you ticked about the date or time. Saving the kit notes that you've seen the new time.
        </div>
      )}

      <section className="card stack-sm before-view no-print" aria-labelledby="before-title">
        <h2 className="section-title" id="before-title">Before the interview</h2>
        <p><strong>{describeWhen(live)}</strong> · {FORMAT_LABEL[kit.format]}{kit.format === "in_person" && kit.location ? ` · ${kit.location}` : ""}</p>
        {kit.meeting_link && (
          <details open={!narrow}>
            <summary>Meeting link</summary>
            <p>{externalHref(kit.meeting_link)
              ? <a href={externalHref(kit.meeting_link)} target="_blank" rel="noopener noreferrer nofollow">{kit.meeting_link}<span className="visually-hidden"> (opens in a new tab)</span></a>
              : <span>{kit.meeting_link}</span>}</p>
          </details>
        )}
        <div className="before-view__grid">
          <div>
            <h3 className="section-title">Examples to bring</h3>
            {kit.stories.length === 0 ? <p className="subtle">None chosen yet.</p> : <ul className="mini-list">{kit.stories.map((s) => <li key={s.id}><Link to={`/stories/${s.id}`} state={fromHere}>{s.title}</Link>{s.short_version && <span className="subtle"> · {s.short_version}</span>}</li>)}</ul>}
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
        <p className="subtle">Afterwards: <Link to={`/applications/${kit.application_id}/events/${kit.event_id}/reflection`} state={fromHere}>reflect on how it went</Link> (private, like this kit).</p>
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
            <p className="subtle">CodeCoach never opens or checks the link. It's kept for you: left out of the printout unless you choose it, and included only in your own data export.</p>
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
                  ) : c.origin === "action" ? (
                    <>
                      {c.action?.recurrence === "weekly" ? (
                        <span>{c.text}<span className="subtle"> · {c.action.occurrences_done} of {c.action.occurrences_total} weeks done</span></span>
                      ) : c.action ? (
                        <label className="checkbox"><input type="checkbox" checked={c.action.done} disabled={actionBusy === c.action.id}
                          onChange={(e) => void toggleAction(c.action!.id, e.target.checked)} />{c.text}</label>
                      ) : <span className="subtle">{c.text}</span>}
                      <Badge>Accepted improvement</Badge>
                      <Link className="subtle" to="/plan#accepted-actions" state={fromHere}>On your plan</Link>
                      <Button size="sm" variant="ghost" aria-label={`Hide “${c.text}”`} onClick={() => set("checklist", kit.checklist.map((x, j) => (j === i ? { ...x, hidden: true } : x)))}>Hide</Button>
                    </>
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
            <AddAction kit={kit} onAdd={(a) => set("checklist", [...kit.checklist, actionItem(a)])} />
            <InlineError error={actionError} />
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
            {live.missing_stories > 0 && (
              <p className="subtle" role="status">
                {live.missing_stories === 1 ? "An example you chose was" : `${live.missing_stories} examples you chose were`} deleted
                from your story bank since, so {live.missing_stories === 1 ? "it isn't" : "they aren't"} in this kit any more.
              </p>
            )}
            {changed.length > 0 && (
              <ul className="kit-story-changes" aria-label="Examples edited since you chose them">
                {changed.map((s) => (
                  <li key={s.id}>
                    <span>“{s.title}” was edited after you chose it (version {s.chosen_revision} then, {s.revision} now).</span>{" "}
                    <Link to={`/stories/${s.id}`} state={fromHere}>Read it</Link>{" "}
                    {reviewed.includes(s.id)
                      ? <span className="subtle">Marked as reread; save the kit to keep that.</span>
                      : <Button size="sm" variant="ghost" onClick={() => { setReviewed((r) => [...r, s.id]); setNotice(""); }}>I've reread it</Button>}
                  </li>
                ))}
              </ul>
            )}
            {pickable.length === 0 ? <p className="subtle">No stories yet. <Link to="/stories/new">Write one</Link>.</p> : (
              <fieldset className="stack-sm">
                <legend className="visually-hidden">Stories</legend>
                {pickable.map((s) => (
                  <label key={s.id} className="checkbox">
                    <input type="checkbox" checked={kit.stories.some((x) => x.id === s.id)}
                      onChange={(e) => set("stories", e.target.checked
                        ? [...kit.stories, { id: s.id, title: s.title, short_version: "", archived: false, revision: 1, chosen_revision: null }]
                        : kit.stories.filter((x) => x.id !== s.id))} />
                    {s.title}{s.archived && <>{" "}<span className="subtle">(archived)</span></>}
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
            <Button variant="primary" loading={busy} disabled={!dirty || conflict !== null} onClick={() => void save()}>Save kit</Button>
            <span className="subtle" role="status">{notice || (dirty ? "Unsaved changes" : kit.saved ? "All changes saved" : "These are suggestions; save to keep your changes")}</span>
            <InlineError error={error} />
          </div>
        </div>

        <aside className="stack">
          <KitTemplatesCard kit={kit} fromHere={fromHere} onApply={(next) => { setKit((x) => ({ ...x, ...next })); setNotice(""); }} />
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
        <PrintPack kit={{ ...kit, ...logistics(live) }} choice={print} unsaved={dirty} />
      </section>
    </div>
  );
}

/** The event's own details, as the server reads them now (they aren't edited on this page). */
function logistics(k: Kit) {
  const { event_title, role_title, employer, on_date, local_time, timezone, starts_at } = k;
  return { event_title, role_title, employer, on_date, local_time, timezone, starts_at };
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

/** A checklist item for an accepted action: its id only is saved; the words and state are the action's. */
function actionItem(a: AcceptedAction): Kit["checklist"][number] {
  const live = a.occurrences.filter((o) => o.status !== "cancelled");
  return {
    id: newId(), origin: "action", action_id: a.id, text: a.title, done: a.status === "done", hidden: false,
    action: {
      id: a.id, title: a.title, recurrence: a.recurrence, done: a.status === "done", href: a.practice_href ?? null,
      occurrences_done: live.filter((o) => o.completed_at).length, occurrences_total: live.length,
    },
  };
}

/** Put an improvement you accepted on this checklist (saved with the kit). */
function AddAction({ kit, onAdd }: { kit: Kit; onAdd: (a: AcceptedAction) => void }) {
  const actions = useActions();
  const [choice, setChoice] = useState("");
  const here = new Set(kit.checklist.map((c) => c.action_id).filter(Boolean));
  const open = (actions.data ?? []).filter((a) => a.status === "open" && !here.has(a.id));
  if (open.length === 0) return null;
  return (
    <div className="row">
      <label className="field">
        <span className="field__label">Add an improvement you accepted</span>
        <select value={choice} onChange={(e) => setChoice(e.target.value)}>
          <option value="">Choose one…</option>
          {open.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}
        </select>
      </label>
      <Button size="sm" disabled={!choice} onClick={() => {
        const a = open.find((x) => x.id === choice);
        if (a) onAdd(a);
        setChoice("");
      }}>Add to checklist</Button>
    </div>
  );
}
