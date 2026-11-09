import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useWorkSample, useWorkSampleAttempts, useWorkSampleDraft } from "@/api/queries";
import type { WorkSampleAttempt, WorkSampleBrief, WorkSampleDraft } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Button } from "@/components/Button";
import { CopyWork } from "@/components/CopyWork";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { VersionConflict } from "@/components/VersionConflict";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { recoveredSave, savedVersion } from "@/lib/conflict";
import { formatDateTime, timeAgo } from "@/lib/format";
import { useCopySince, writeCopy } from "@/lib/deviceCopies";
import { useRequestKey } from "@/lib/requestKey";

import { Debrief } from "./Debrief";

type Sections = Record<string, string>;
const countWords = (text: string) => (text.match(/[\p{L}\p{N}][\p{L}\p{N}'’$%.-]*/gu) ?? []).length;
const fp = (s: Sections) => JSON.stringify(Object.keys(s).sort().map((k) => [k, (s[k] ?? "").trim()]));

export function WorkSamplePage() {
  const { briefId = "" } = useParams();
  const brief = useWorkSample(briefId);
  const draft = useWorkSampleDraft(briefId);
  if (brief.isPending || draft.isPending) return <LoadingState label="Loading the brief…" />;
  if (brief.isError) return <div className="page"><ErrorState error={brief.error} onRetry={() => void brief.refetch()} /></div>;
  if (draft.isError) return <div className="page"><ErrorState error={draft.error} onRetry={() => void draft.refetch()} /></div>;
  return <Writer key={briefId} brief={brief.data} initial={draft.data} />;
}

function Writer({ brief, initial }: { brief: WorkSampleBrief; initial: WorkSampleDraft }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const localKey = `work-sample-draft:${user?.id ?? "anon"}:${brief.id}`;
  const since = useCopySince(localKey); // a copy removed from "Your data" after this opened isn't written back
  const sectionDefs = brief.sections.length ? brief.sections : [{ id: "message", label: "Your message", hint: "" }];
  const [sections, setSections] = useState<Sections>(initial.sections);
  const [saved, setSaved] = useState({ fp: fp(initial.sections), revision: initial.revision });
  const [recovery, setRecovery] = useState<Sections | null>(() => {
    try {
      const kept = JSON.parse(localStorage.getItem(localKey) ?? "null") as { sections: Sections; base: number } | null;
      return kept && fp(kept.sections) !== fp(initial.sections) ? kept.sections : null;
    } catch {
      return null;
    }
  });
  const [keptHere, setKeptHere] = useState(true);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<"save" | "send" | null>(null);
  const [against, setAgainst] = useState<WorkSampleDraft | null>(null);
  const [earlierSave, setEarlierSave] = useState<number | null>(null);
  const [preview, setPreview] = useState(false);
  const [shown, setShown] = useState<WorkSampleAttempt | null>(null);
  const attempts = useWorkSampleAttempts(brief.id);
  const saveKey = useRequestKey();
  const focusAfter = useRef<string | null>(null);
  const dirty = fp(sections) !== saved.fp;
  useLeaveWarning(dirty);
  const total = countWords(Object.values(sections).join(" "));

  useEffect(() => {
    if (dirty && !recovery) {
      const ok = writeCopy(localKey, JSON.stringify({ sections, base: saved.revision }), since);
      queueMicrotask(() => setKeptHere(ok));
    }
  }, [sections, dirty, recovery, localKey, saved.revision, since]);
  useEffect(() => {
    if (!focusAfter.current) return;
    document.getElementById(focusAfter.current)?.focus();
    focusAfter.current = null;
  });

  function adopt(d: WorkSampleDraft) {
    setSections(d.sections);
    setSaved({ fp: fp(d.sections), revision: d.revision });
    qc.setQueryData(["me", "work-samples", "draft", brief.id], d);
    try { localStorage.removeItem(localKey); } catch { /* blocked */ }
    setAgainst(null);
    setEarlierSave(null);
  }

  async function save(revision = saved.revision): Promise<boolean> {
    setError(null);
    const sent = { sections, expected_revision: revision };
    const sentFp = fp(sections);
    try {
      const out = await api.saveWorkSampleDraft(brief.id, { ...sent, client_request_id: saveKey.keyFor([brief.id, sent]) });
      saveKey.done();
      const recovered = recoveredSave(out);
      if (recovered?.newer) {
        setEarlierSave(recovered.accepted);
        setAgainst(out);
        return false;
      }
      setSaved({ fp: sentFp, revision: out.revision });
      qc.setQueryData(["me", "work-samples", "draft", brief.id], out);
      try { localStorage.removeItem(localKey); } catch { /* blocked */ }
      setAgainst(null);
      setStatus(recovered ? `Your earlier save went through (version ${recovered.accepted}).` : "Saved to your account.");
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.code === "stale_revision") {
        setAgainst(savedVersion<WorkSampleDraft>(e.details) ?? (await api.workSampleDraft(brief.id).catch(() => null)));
      } else {
        setError(e);
      }
      return false;
    }
  }

  async function saveNow(revision?: number) {
    setBusy("save");
    try { await save(revision); } finally { setBusy(null); }
  }

  async function send() {
    setBusy("send");
    setError(null);
    try {
      if (dirty && !(await save())) return;
      const latest = attempts.data?.[0]?.id ?? null;
      const a = await api.sendWorkSample(brief.id, { sections, revision_of: latest });
      setShown(a);
      void attempts.refetch();
      setStatus(latest ? "Sent as a revision. Your earlier attempt is kept as it was." : "Sent. Your feedback is below.");
      focusAfter.current = "ws-feedback";
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  const asText = sectionDefs.map((s) => (brief.sections.length ? `${s.label}\n${sections[s.id] ?? ""}` : sections[s.id] ?? "")).join("\n\n");
  const inWords = (s: Sections) => sectionDefs.map((d) => `${d.label}: ${s[d.id] ?? ""}`).join("\n");
  const SAVED = "Saved to your account.";
  const shownStatus = status === SAVED && dirty ? "" : status;
  const inLimits = total >= brief.min_words && total <= brief.max_words;

  return (
    <div className="page ws-page">
      <BackLink fallback={{ to: "/work-samples", label: "Work samples" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">WORK SAMPLE · {brief.format_label.toUpperCase()}</p>
          <h1 className="page__title">{brief.title}</h1>
          <p className="page__subtitle">Write the work itself, for the reader named in the brief, using only the facts it gives. It's practice: nothing is sent to anyone.</p>
        </div>
      </div>
      <p className="banner banner--info" role="note">{brief.scope_note} A finished work sample is practice evidence, not a credential.</p>

      {recovery && (
        <div className="banner banner--info row" role="region" aria-label="Unsaved changes">
          <span>You have unsaved changes to this work sample on this device.</span>
          <span className="row">
            <Button size="sm" variant="primary" onClick={() => { setSections(recovery); setRecovery(null); }}>Restore them</Button>
            <Button size="sm" variant="ghost" onClick={() => { try { localStorage.removeItem(localKey); } catch { /* blocked */ } setRecovery(null); }}>Discard them</Button>
          </span>
        </div>
      )}

      <div className="ws-layout">
        <section className="card stack-sm ws-brief" aria-labelledby="ws-brief-title">
          <h2 className="section-title" id="ws-brief-title">The brief</h2>
          <p>{brief.scenario}</p>
          <p><strong>Who it's for:</strong> {brief.audience}</p>
          <p><strong>What it's for:</strong> {brief.purpose}</p>
          <h3 className="review-minor">Facts you can use</h3>
          <ul className="mini-list">{brief.facts.map((f) => <li key={f}>{f}</li>)}</ul>
          <h3 className="review-minor">The brief asks you to cover</h3>
          <ul className="mini-list">{brief.required.map((r) => <li key={r}>{r}</li>)}</ul>
          <p className="subtle">{brief.min_words} to {brief.max_words} words. {brief.review_status}</p>
        </section>

        <section className="stack-sm" aria-labelledby="ws-editor-title">
          <div className="row ws-toolbar">
            <h2 className="section-title" id="ws-editor-title">Your {brief.format_label.toLowerCase()}</h2>
            <Button size="sm" variant="ghost" aria-pressed={preview} onClick={() => setPreview((p) => !p)}>{preview ? "Back to editing" : "Preview"}</Button>
          </div>
          {preview ? (
            <article className="card stack-sm ws-preview" aria-label="Preview">
              {sectionDefs.map((s) => (
                <div key={s.id} className="stack-sm">
                  {brief.sections.length > 0 && <h3 className="review-minor">{s.label}</h3>}
                  {(sections[s.id] ?? "").split(/\n{2,}/).filter((p) => p.trim()).map((p, i) => <p key={i} className="ws-text">{p}</p>)}
                </div>
              ))}
              <p className="subtle">Only you can see this. Copying it is up to you; nothing is sent.</p>
              <CopyWork text={asText} label="Copy as text" />
            </article>
          ) : (
            sectionDefs.map((s) => (
              <label key={s.id} className="field" htmlFor={`ws-${s.id}`}>
                <span className="field__label">{s.label}</span>
                {s.hint && <span className="subtle">{s.hint}</span>}
                <textarea id={`ws-${s.id}`} className="input" rows={brief.sections.length ? 3 : 10} maxLength={4000} value={sections[s.id] ?? ""}
                  onChange={(e) => setSections((cur) => ({ ...cur, [s.id]: e.target.value }))} />
              </label>
            ))
          )}
          <p className={inLimits ? "subtle" : "field__error"} aria-live="polite">{total} words (the brief asks for {brief.min_words} to {brief.max_words}).</p>
          <div className="row">
            <Button variant="secondary" loading={busy === "save"} disabled={!dirty} onClick={() => void saveNow()}>Save draft</Button>
            <Button variant="primary" loading={busy === "send"} onClick={() => void send()}>{attempts.data?.length ? "Send the revision for feedback" : "Get feedback"}</Button>
            <span className="subtle" role="status">{shownStatus || (dirty ? (keptHere ? "Unsaved changes, kept on this device" : "Unsaved changes, and this browser can't keep a copy: save, or copy your work") : saved.revision ? "Saved to your account" : "")}</span>
          </div>
          {against && (
            <VersionConflict what="work sample" earlierSave={earlierSave} savedWhen={`version ${against.revision}${against.updated_at ? `, ${timeAgo(against.updated_at)}` : ""}`}
              busy={busy === "save"} keepMineLabel="Keep mine as the newest"
              fields={[{ label: "Your work sample", mine: inWords(sections), saved: inWords(against.sections) }]}
              onKeepMine={() => void saveNow(against.revision)} onUseSaved={() => adopt(against)} />
          )}
          <InlineError error={error} />
        </section>
      </div>

      {shown && (
        <section className="stack" aria-labelledby="ws-feedback">
          <h2 className="section-title" id="ws-feedback" tabIndex={-1}>Feedback on {formatDateTime(shown.created_at)}{shown.revision_of ? " (a revision)" : ""}</h2>
          {shown.current_version != null && shown.current_version !== shown.brief_version && (
            <p className="subtle">Written against version {shown.brief_version} of this brief; it's version {shown.current_version} now.</p>
          )}
          <Debrief attempt={shown} />
        </section>
      )}

      {attempts.data && attempts.data.length > 0 && (
        <section className="card stack-sm" aria-labelledby="ws-earlier">
          <h2 className="section-title" id="ws-earlier">Your attempts</h2>
          <ul className="mini-list">
            {attempts.data.map((a) => (
              <li key={a.id}>
                <button type="button" className="link-button" onClick={async () => { const full = await api.workSampleAttempt(a.id).catch(() => null); if (full) { setShown(full); focusAfter.current = "ws-feedback"; } }}>
                  {formatDateTime(a.created_at)}
                </button>
                <span className="subtle"> · covers {a.covered} of {a.total} points{a.revision_of ? " · a revision" : ""} · version {a.brief_version}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
