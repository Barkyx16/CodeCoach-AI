import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useReviewAttempts, useReviewDraft, useReviewExercise } from "@/api/queries";
import type { ReviewAttempt, ReviewDraft, ReviewExercise, ReviewFeedback, ReviewFinding, ReviewReference } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { CopyWork } from "@/components/CopyWork";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { VersionConflict } from "@/components/VersionConflict";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { recoveredSave, savedVersion } from "@/lib/conflict";
import { formatArgs, formatDateTime, formatValue, timeAgo } from "@/lib/format";
import { useRequestKey } from "@/lib/requestKey";

import { CodeView, ComparisonView, ReferenceView } from "./Comparison";
import { where } from "./where";

/** A finding as the form holds it: line numbers as typed, so a half-typed number isn't lost. */
interface Row {
  id: string;
  start: string;
  end: string;
  problem: string;
  consequence: string;
  repair: string;
  anchor?: ReviewFinding["anchor"];
}
interface Work { rows: Row[]; summary: string }

const newId = () => `f${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
const toRow = (f: ReviewFinding): Row => ({
  id: f.id, start: String(f.start_line), end: String(f.end_line), problem: f.problem, consequence: f.consequence, repair: f.repair, anchor: f.anchor,
});
const fingerprint = (w: Work) => JSON.stringify([w.rows.map(({ anchor: _a, ...r }) => r), w.summary.trim()]);
const fromDraft = (d: ReviewDraft): Work => ({ rows: d.findings.map(toRow), summary: d.summary });

/** A row's lines, if they're whole numbers inside the code; otherwise what's wrong with them. */
function span(row: Row, lineCount: number): [number, number] | string {
  const start = Number(row.start);
  const end = row.end.trim() ? Number(row.end) : start;
  if (!Number.isInteger(start) || !Number.isInteger(end)) return "Give the lines as whole numbers.";
  if (start < 1 || end > lineCount) return `The code has lines 1 to ${lineCount}.`;
  if (end < start) return "The last line comes before the first.";
  return [start, end];
}

export function ReviewPage() {
  const { slug = "" } = useParams();
  const exercise = useReviewExercise(slug);
  const draft = useReviewDraft(slug);
  if (exercise.isPending || draft.isPending) return <LoadingState label="Loading the review exercise…" />;
  if (exercise.isError) return <div className="page"><ErrorState error={exercise.error} onRetry={() => void exercise.refetch()} /></div>;
  if (draft.isError) return <div className="page"><ErrorState error={draft.error} onRetry={() => void draft.refetch()} /></div>;
  return <Review key={slug} exercise={exercise.data} initial={draft.data} />;
}

function Review({ exercise, initial }: { exercise: ReviewExercise; initial: ReviewDraft }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const localKey = `code-review-draft:${user?.id ?? "anon"}:${exercise.slug}`;
  const codeLines = exercise.code.split("\n");
  const [work, setWork] = useState<Work>(() => fromDraft(initial));
  const [saved, setSaved] = useState({ fp: fingerprint(fromDraft(initial)), revision: initial.revision });
  const [recovery, setRecovery] = useState<(Work & { base: number }) | null>(() => {
    try {
      const raw = localStorage.getItem(localKey);
      const kept = raw ? (JSON.parse(raw) as Work & { base: number }) : null;
      return kept && Array.isArray(kept.rows) && fingerprint(kept) !== fingerprint(fromDraft(initial)) ? kept : null;
    } catch {
      return null; // unreadable or blocked storage: nothing to offer
    }
  });
  const [keptHere, setKeptHere] = useState(true);
  const [active, setActive] = useState<number | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<"save" | "send" | "reveal" | null>(null);
  const [against, setAgainst] = useState<ReviewDraft | null>(null);
  const [earlierSave, setEarlierSave] = useState<number | null>(null);
  const [asking, setAsking] = useState(false);
  const [reference, setReference] = useState<ReviewReference | null>(null);
  const [attempt, setAttempt] = useState<ReviewAttempt | null>(null);
  const [revealed, setRevealed] = useState(initial.revealed);
  const attempts = useReviewAttempts(exercise.slug);
  const saveKey = useRequestKey();
  const focusAfter = useRef<string | null>(null);
  const dirty = fingerprint(work) !== saved.fp;
  useLeaveWarning(dirty);

  // Unsaved work is also kept on this device, so a closed tab or a crash loses nothing.
  useEffect(() => {
    if (dirty && !recovery) {
      let ok = true;
      try { localStorage.setItem(localKey, JSON.stringify({ ...work, base: saved.revision })); } catch { ok = false; }
      queueMicrotask(() => setKeptHere(ok));
    }
  }, [work, dirty, recovery, localKey, saved.revision]);
  useEffect(() => {
    if (!focusAfter.current) return;
    document.getElementById(focusAfter.current)?.focus();
    focusAfter.current = null;
  });

  const problems = work.rows.map((r) => span(r, exercise.line_count));
  const linesOk = problems.every((p) => typeof p !== "string");
  const payload = () => ({
    findings: work.rows.map((r, i) => {
      const [start, end] = problems[i] as [number, number];
      return { id: r.id, start_line: start, end_line: end, problem: r.problem, consequence: r.consequence, repair: r.repair };
    }),
    summary: work.summary,
  });
  const update = (i: number, patch: Partial<Row>) =>
    setWork((w) => ({ ...w, rows: w.rows.map((r, j) => (j === i ? { ...r, ...patch, anchor: undefined } : r)) }));

  function adopt(d: ReviewDraft) {
    const w = fromDraft(d);
    setWork(w);
    setSaved({ fp: fingerprint(w), revision: d.revision });
    qc.setQueryData(["me", "code-reviews", "draft", exercise.slug], d);
    try { localStorage.removeItem(localKey); } catch { /* blocked */ }
    setAgainst(null);
    setEarlierSave(null);
  }

  /** Saves the draft; false if it didn't (a conflict or an error is on the page). */
  async function save(revision = saved.revision): Promise<boolean> {
    setError(null);
    const sent = { ...payload(), expected_revision: revision };
    const fp = fingerprint(work);
    try {
      const out = await api.saveReviewDraft(exercise.slug, { ...sent, client_request_id: saveKey.keyFor([exercise.slug, sent]) });
      saveKey.done();
      const recovered = recoveredSave(out);
      if (recovered?.newer) {
        setEarlierSave(recovered.accepted);
        setAgainst(out);
        return false;
      }
      setSaved({ fp, revision: out.revision });
      qc.setQueryData(["me", "code-reviews", "draft", exercise.slug], out);
      try { localStorage.removeItem(localKey); } catch { /* blocked */ }
      setAgainst(null);
      setEarlierSave(null);
      setStatus(recovered ? `Your earlier save went through (version ${recovered.accepted}).` : "Saved to your account.");
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.code === "stale_revision") {
        setEarlierSave(null);
        setAgainst(savedVersion<ReviewDraft>(e.details) ?? (await api.reviewDraft(exercise.slug).catch(() => null)));
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
      if (dirty && !(await save())) return; // the draft is the copy that survives a reload
      const a = await api.sendReview(exercise.slug, payload());
      setAttempt(a);
      setReference(null);
      setRevealed(true);
      setStatus("Sent. The comparison is below; your review is kept with the code it reviewed.");
      void attempts.refetch();
      focusAfter.current = "review-result";
    } catch (e) {
      setError(e); // the review stays on the page and on this device
    } finally {
      setBusy(null);
    }
  }

  async function reveal() {
    setBusy("reveal");
    setError(null);
    try {
      setReference(await api.revealReview(exercise.slug));
      setAttempt(null);
      setAsking(false);
      setRevealed(true);
      focusAfter.current = "review-result";
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  function addFinding() {
    const id = newId();
    setWork((w) => ({ ...w, rows: [...w.rows, { id, start: "", end: "", problem: "", consequence: "", repair: "" }] }));
    setActive(work.rows.length);
    focusAfter.current = `${id}-start`;
  }

  function removeFinding(i: number) {
    setWork((w) => ({ ...w, rows: w.rows.filter((_, j) => j !== i) }));
    setActive(null);
    const next = work.rows[i + 1] ?? work.rows[i - 1];
    if (next) focusAfter.current = `${next.id}-start`;
    else focusAfter.current = "review-add";
    setStatus(`Finding ${i + 1} removed.`);
  }

  const inWords = (w: Work) => w.rows.map((r, i) => `Finding ${i + 1} (lines ${r.start}–${r.end || r.start}): ${r.problem}\n${r.consequence}\n${r.repair}`).join("\n\n") + (w.summary ? `\n\nSummary: ${w.summary}` : "");
  const SAVED = "Saved to your account.";
  const shownStatus = status === SAVED && dirty ? "" : status;
  const cited = active != null && typeof problems[active] !== "string" ? (problems[active] as [number, number]) : null;
  const moved = initial.exercise_version !== initial.current_version;

  return (
    <div className="page review-page">
      <BackLink fallback={{ to: "/problems?view=code-review", label: "Code review exercises" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">CODE REVIEW · YOU'RE THE REVIEWER</p>
          <h1 className="page__title">{exercise.title}</h1>
          <p className="page__subtitle">
            Someone else wrote this code. Write what you'd tell them before it's merged: where, what's wrong, what happens, and what to change.
            This isn't the coach reviewing your code, and nothing here is sent to anyone.
          </p>
        </div>
      </div>

      {recovery && (
        <div className="banner banner--info row" role="region" aria-label="Unsaved changes">
          <span>You have unsaved changes to this review on this device.</span>
          <span className="row">
            <Button size="sm" variant="primary" onClick={() => {
              setWork({ rows: recovery.rows, summary: recovery.summary });
              setRecovery(null);
              if (recovery.base !== saved.revision) setAgainst(initial); // kept against an older save: compare first
            }}>Restore them</Button>
            <Button size="sm" variant="ghost" onClick={() => { try { localStorage.removeItem(localKey); } catch { /* blocked */ } setRecovery(null); }}>Discard them</Button>
          </span>
        </div>
      )}
      {moved && (
        <div className="banner banner--warning" role="note">
          This exercise was corrected after you started (version {initial.exercise_version} → {initial.current_version}).
          Findings whose code was found again now point at its new lines; check any marked as not found.
        </div>
      )}

      <div className="review-layout">
        <section className="stack-sm" aria-labelledby="review-task-title">
          <Card className="stack-sm">
            <h2 className="section-title" id="review-task-title">The task</h2>
            <p>{exercise.context}</p>
            <details>
              <summary>The problem: {exercise.problem_title}</summary>
              <div className="markdown"><Markdown>{exercise.statement}</Markdown></div>
              {exercise.constraints.length > 0 && <ul className="mini-list">{exercise.constraints.map((c) => <li key={c}><code>{c}</code></li>)}</ul>}
            </details>
            <h3 className="review-minor">The problem's public tests</h3>
            <ol className="mini-list review-tests">
              {exercise.public_tests.map((t) => (
                <li key={t.position}><code>{formatArgs(t.input)}</code> should give <code>{formatValue(t.expected_output)}</code></li>
              ))}
            </ol>
          </Card>
          <h2 className="section-title" id="review-code-title">The code</h2>
          <p className="subtle" aria-live="polite">{cited ? `Showing ${where(...cited)} of finding ${(active ?? 0) + 1}.` : `${exercise.line_count} lines. Cite them by number in each finding.`}</p>
          <CodeView code={exercise.code} cited={cited} label={`The code under review, ${exercise.line_count} lines, with line numbers`} />
        </section>

        <section className="stack-sm" aria-labelledby="review-findings-title">
          <h2 className="section-title" id="review-findings-title">Your review</h2>
          <p className="subtle">One finding per point. A short review with evidence helps more than a long list, and you don't need to rate severity. If the code looks right, say so in the summary.</p>
          {work.rows.length === 0 && <p>No findings yet.</p>}
          <ol className="stack-sm review-findings">
            {work.rows.map((r, i) => {
              const s = problems[i] ?? "";
              const bad = typeof s === "string" && (r.start !== "" || r.end !== "");
              const excerpt = typeof s === "string" ? null : codeLines.slice(s[0] - 1, s[1]).join("\n");
              return (
                <li key={r.id} className="card stack-sm review-finding" onFocus={() => setActive(i)}>
                  <fieldset className="stack-sm">
                    <legend className="review-finding__legend">Finding {i + 1}</legend>
                    <div className="row review-lines">
                      <label className="field" htmlFor={`${r.id}-start`}><span className="field__label">From line</span>
                        <input id={`${r.id}-start`} className="input" inputMode="numeric" value={r.start} aria-invalid={bad || undefined}
                          aria-describedby={bad ? `${r.id}-lines-error` : undefined} onChange={(e) => update(i, { start: e.target.value })} />
                      </label>
                      <label className="field" htmlFor={`${r.id}-end`}><span className="field__label">To line</span>
                        <input id={`${r.id}-end`} className="input" inputMode="numeric" value={r.end} placeholder={r.start} aria-invalid={bad || undefined}
                          aria-describedby={bad ? `${r.id}-lines-error` : undefined} onChange={(e) => update(i, { end: e.target.value })} />
                      </label>
                    </div>
                    {bad && <p className="field__error" id={`${r.id}-lines-error`}>{s}</p>}
                    {r.anchor === "moved" && <p className="subtle">Moved to {excerpt != null ? where(...(s as [number, number])) : "new lines"} to follow the code you cited.</p>}
                    {r.anchor === "missing" && <p className="field__error">The code you cited isn't in the corrected version. Check this finding's lines.</p>}
                    {excerpt != null && <pre className="code-block review-excerpt" aria-label={`The code at ${where(...(s as [number, number]))}`}>{excerpt}</pre>}
                    <label className="field" htmlFor={`${r.id}-problem`}><span className="field__label">What's wrong</span>
                      <textarea id={`${r.id}-problem`} className="input" rows={2} maxLength={2000} value={r.problem} onChange={(e) => update(i, { problem: e.target.value })} />
                    </label>
                    <label className="field" htmlFor={`${r.id}-consequence`}><span className="field__label">What happens because of it</span>
                      <span className="subtle">Which input goes wrong, and how? A public test number is good evidence.</span>
                      <textarea id={`${r.id}-consequence`} className="input" rows={2} maxLength={2000} value={r.consequence} onChange={(e) => update(i, { consequence: e.target.value })} />
                    </label>
                    <label className="field" htmlFor={`${r.id}-repair`}><span className="field__label">What to change</span>
                      <span className="subtle">A change, or a test that would show the problem.</span>
                      <textarea id={`${r.id}-repair`} className="input" rows={2} maxLength={2000} value={r.repair} onChange={(e) => update(i, { repair: e.target.value })} />
                    </label>
                    <p><Button size="sm" variant="ghost" onClick={() => removeFinding(i)} aria-label={`Remove finding ${i + 1}`}>Remove</Button></p>
                  </fieldset>
                </li>
              );
            })}
          </ol>
          <p><Button id="review-add" variant="secondary" onClick={addFinding} disabled={work.rows.length >= 20}>Add a finding</Button></p>
          <label className="field" htmlFor="review-summary"><span className="field__label">Summary (optional)</span>
            <span className="subtle">Anything overall, for example that you found no defect.</span>
            <textarea id="review-summary" className="input" rows={2} maxLength={2000} value={work.summary} onChange={(e) => setWork((w) => ({ ...w, summary: e.target.value }))} />
          </label>
          <div className="row review-actions">
            <Button variant="secondary" loading={busy === "save"} disabled={!dirty || !linesOk} onClick={() => void saveNow()}>Save draft</Button>
            <Button variant="primary" loading={busy === "send"} disabled={!linesOk} onClick={() => void send()}>Send review and compare</Button>
            <span className="subtle" role="status">{shownStatus || (dirty ? (keptHere ? "Unsaved changes, kept on this device" : "Unsaved changes, and this browser can't keep a copy: save, or copy your work") : saved.revision ? "Saved to your account" : "")}</span>
            {dirty && !keptHere && <CopyWork text={inWords(work)} label="Copy your review" />}
          </div>
          {!linesOk && <p className="subtle">Fix the line numbers above to save or send.</p>}
          {asking ? (
            <div className="banner banner--info stack-sm" role="group" aria-label="Show the authored review?">
              <p>This shows the authored review: its defects with their test evidence, and its preferences. You can still revise and send your own;
                reviews you send afterwards say they were written after reading it.</p>
              <span className="row">
                <Button size="sm" variant="primary" loading={busy === "reveal"} onClick={() => void reveal()}>Show the authored review</Button>
                <Button size="sm" variant="ghost" onClick={() => setAsking(false)}>Not yet</Button>
              </span>
            </div>
          ) : (
            <p><Button size="sm" variant="ghost" onClick={() => setAsking(true)}>{revealed ? "Show the authored review again" : "Stuck? Show the authored review"}</Button></p>
          )}
          {against && (
            <VersionConflict what="review" earlierSave={earlierSave} savedWhen={`version ${against.revision}${against.updated_at ? `, ${timeAgo(against.updated_at)}` : ""}`}
              busy={busy === "save"} keepMineLabel="Keep mine as the newest"
              fields={[{ label: "Your review in words", mine: inWords(work), saved: inWords(fromDraft(against)) }]}
              onKeepMine={() => void saveNow(against.revision)}
              onUseSaved={() => adopt(against)} />
          )}
          <InlineError error={error} />
        </section>
      </div>

      {(attempt || reference) && (
        <section className="card stack review-result" aria-labelledby="review-result">
          <h2 className="section-title" id="review-result" tabIndex={-1}>{attempt ? "Your review and the authored one" : "The authored review"}</h2>
          {attempt ? (
            <ComparisonView findings={attempt.findings} summary={attempt.summary} feedback={attempt.feedback as unknown as ReviewFeedback}
              reference={attempt.reference} afterReveal={attempt.after_reveal} />
          ) : reference && <ReferenceView reference={reference} heading="What the author of this exercise found" />}
          <p>Revise your findings above and send again if you like: the comparison is by where a finding points, not its wording.</p>
        </section>
      )}

      {attempts.data && attempts.data.length > 0 && (
        <section className="card stack-sm" aria-labelledby="review-earlier">
          <h2 className="section-title" id="review-earlier">Your earlier reviews</h2>
          <ul className="mini-list">
            {attempts.data.map((a) => (
              <li key={a.id}>
                <Link to={`/code-reviews/attempts/${a.id}`}>{formatDateTime(a.created_at)}</Link>
                <span className="subtle"> · {a.findings} finding{a.findings === 1 ? "" : "s"}
                  {a.defects_total ? ` · points at ${a.defects_raised} of ${a.defects_total} authored defect${a.defects_total === 1 ? "" : "s"}` : " · no authored defect"}
                  {a.after_reveal ? " · after reading the authored review" : ""} · version {a.exercise_version}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="subtle">{exercise.review_status} Exercise version {exercise.version}.</p>
    </div>
  );
}
