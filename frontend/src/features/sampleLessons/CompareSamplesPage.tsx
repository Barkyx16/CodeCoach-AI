import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useSampleLesson, useSampleReadings } from "@/api/queries";
import type { ComparisonAttempt, ComparisonExplanation, ComparisonFeedback, ComparisonLesson } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { formatDateTime } from "@/lib/format";

type Kind = "strength" | "gap";
interface Mark { kind: Kind; reason: string }
type Marks = Record<string, Mark>; // "A/a2" -> mark
interface Draft { marks: Marks; choice: string | null }

const keyOf = (sample: string, sentence: string) => `${sample}/${sentence}`;
const words = (t: string) => (t.match(/[\p{L}\p{N}']+/gu) ?? []).length;
const STATUS: Record<ComparisonFeedback["selections"][number]["status"], { text: string; tone: string }> = {
  matches: { text: "Matches the explanation", tone: "success" },
  differs: { text: "The explanation reads it differently", tone: "warning" },
  not_covered: { text: "Not covered by the explanation", tone: "neutral" },
};

export function CompareSamplesPage() {
  const { lessonId = "" } = useParams();
  const lesson = useSampleLesson(lessonId);
  if (lesson.isPending) return <LoadingState label="Loading the lesson…" />;
  if (lesson.isError) return <div className="page"><ErrorState error={lesson.error} onRetry={() => void lesson.refetch()} /></div>;
  return <Compare key={lessonId} lesson={lesson.data} />;
}

function Compare({ lesson }: { lesson: ComparisonLesson }) {
  const { user } = useAuth();
  const draftKey = `compare-draft:${user?.id ?? "anon"}:${lesson.id}:v${lesson.version}`;
  const [restored] = useState<Draft | null>(() => {
    try { return JSON.parse(localStorage.getItem(draftKey) ?? "null") as Draft | null; } catch { return null; }
  });
  const [marks, setMarks] = useState<Marks>(restored?.marks ?? {});
  const [choice, setChoice] = useState<string | null>(restored?.choice ?? null);
  const [explanation, setExplanation] = useState<ComparisonExplanation | null>(null);
  const [asking, setAsking] = useState(false);
  const [result, setResult] = useState<ComparisonAttempt | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(restored && Object.keys(restored.marks).length ? "Your unsent marks were restored from this device." : "");
  const [open, setOpen] = useState<string>(lesson.samples[0]?.id ?? ""); // narrow screens: one sample at a time
  const wide = useMediaQuery("(min-width: 900px)");
  const readings = useSampleReadings(lesson.id);
  const focusAfter = useRef<string | null>(null);
  const marked = Object.entries(marks);
  useLeaveWarning(marked.length > 0 && !result);

  useEffect(() => {
    try {
      if (marked.length || choice) localStorage.setItem(draftKey, JSON.stringify({ marks, choice }));
      else localStorage.removeItem(draftKey);
    } catch { /* blocked: they last as long as the page */ }
  }, [marks, choice, draftKey, marked.length]);
  useEffect(() => {
    if (!focusAfter.current) return;
    document.getElementById(focusAfter.current)?.focus();
    focusAfter.current = null;
  });

  const toggle = (k: string, kind: Kind) => setMarks((m) => {
    const next = { ...m };
    if (next[k]?.kind === kind) delete next[k];
    else next[k] = { kind, reason: next[k]?.reason ?? "" };
    return next;
  });
  const missingReasons = marked.filter(([, m]) => words(m.reason) < 3).length;
  const countFor = (sample: string) => {
    const n = marked.filter(([k]) => k.startsWith(`${sample}/`)).length;
    return n ? `${n} marked` : "nothing marked yet";
  };

  async function send() {
    setError(null);
    if (!marked.length) { setStatus("Mark at least one excerpt as a strength or a gap first."); return; }
    if (missingReasons) { setStatus("Each marked excerpt needs a reason (a few words)."); return; }
    setBusy(true);
    try {
      const selections = marked.map(([k, m]) => {
        const [sample = "", sentence = ""] = k.split("/");
        return { sample, sentence, kind: m.kind, reason: m.reason };
      });
      const a = await api.sendSampleReading(lesson.id, { selections, choice: lesson.kind === "clear" ? choice : null, revealed_early: explanation !== null });
      setResult(a);
      setMarks({});
      setChoice(null);
      setStatus("Sent. Your reading is kept with this version of the samples.");
      void readings.refetch();
      focusAfter.current = "cmp-result";
    } catch (e) {
      setError(e); // the marks stay on the page and on this device
    } finally {
      setBusy(false);
    }
  }

  async function revealNow() {
    try {
      setExplanation(await api.sampleLessonExplanation(lesson.id));
      setAsking(false);
      focusAfter.current = "cmp-explanation";
    } catch (e) {
      setError(e);
    }
  }

  const shownExplanation = (result?.explanation as unknown as ComparisonExplanation | undefined) ?? explanation;
  const sentenceText = (sample: string, sentence: string) =>
    (result?.samples ?? lesson.samples).find((s) => s.id === sample)?.sentences.find((x) => x.id === sentence)?.text ?? "";
  const rubricLabel = (id: string) => (result?.rubric ?? lesson.rubric).find((r) => r.id === id)?.label ?? id;

  return (
    <div className="page cmp-page">
      <BackLink fallback={{ to: "/compare", label: "Compare sample answers" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">COMPARE SAMPLE ANSWERS</p>
          <h1 className="page__title">{lesson.title}</h1>
          <p className="page__subtitle">{lesson.teaching_goal} Mark what helps or hurts each answer and say why, then compare with an explanation. Length and confidence aren't the point; evidence is.</p>
        </div>
      </div>
      <section className="card stack-sm" aria-labelledby="cmp-question">
        <h2 className="section-title" id="cmp-question">The question</h2>
        <p className="cmp-question">{lesson.question}</p>
        <h3 className="review-minor">What a useful answer does</h3>
        <ul className="mini-list">{lesson.rubric.map((r) => <li key={r.id}>{r.label}</li>)}</ul>
        <p className="subtle">{lesson.review_status}</p>
      </section>

      <div className="cmp-samples">
        {lesson.samples.map((s) => (
          <section key={s.id} className="card stack-sm cmp-sample" aria-labelledby={`cmp-${s.id}`}>
            <h2 className="section-title" id={`cmp-${s.id}`}>
              {wide ? s.label : (
                <button type="button" className="cmp-sample__toggle" aria-expanded={open === s.id} aria-controls={`cmp-sentences-${s.id}`}
                  onClick={() => setOpen(open === s.id ? "" : s.id)}>
                  <span aria-hidden="true" className="cmp-sample__chevron">{open === s.id ? "▾" : "▸"}</span>{s.label}<span className="subtle"> · {countFor(s.id)}</span>
                </button>
              )}
            </h2>
            <ol id={`cmp-sentences-${s.id}`} className="cmp-sentences" hidden={!wide && open !== s.id} aria-label={`${s.label}, sentence by sentence`}>
              {s.sentences.map((x) => {
                const k = keyOf(s.id, x.id);
                const m = marks[k];
                return (
                  <li key={x.id} className={`cmp-sentence${m ? ` is-${m.kind}` : ""}`}>
                    <p className="cmp-sentence__text">{x.text}</p>
                    <span className="row cmp-sentence__marks" role="group" aria-label={`Mark this sentence from ${s.label}`}>
                      <Button size="sm" variant={m?.kind === "strength" ? "primary" : "ghost"} aria-pressed={m?.kind === "strength"} onClick={() => toggle(k, "strength")}>Strength</Button>
                      <Button size="sm" variant={m?.kind === "gap" ? "primary" : "ghost"} aria-pressed={m?.kind === "gap"} onClick={() => toggle(k, "gap")}>Gap</Button>
                    </span>
                    {m && (
                      <label className="field" htmlFor={`cmp-reason-${k}`}><span className="field__label">Why is it a {m.kind}?</span>
                        <textarea id={`cmp-reason-${k}`} className="input" rows={2} maxLength={600} value={m.reason}
                          aria-invalid={words(m.reason) < 3 && status.startsWith("Each") ? true : undefined}
                          onChange={(e) => setMarks((cur) => ({ ...cur, [k]: { ...m, reason: e.target.value } }))} />
                      </label>
                    )}
                  </li>
                );
              })}
            </ol>
          </section>
        ))}
      </div>

      <section className="card stack-sm" aria-labelledby="cmp-choice">
        <h2 className="section-title" id="cmp-choice">{lesson.kind === "clear" ? "Which answer is more useful? (optional)" : "No single best answer"}</h2>
        {lesson.kind === "clear" ? (
          <fieldset className="row cmp-choice">
            <legend className="visually-hidden">Which answer is more useful</legend>
            {lesson.samples.map((s) => (
              <label key={s.id} className="row"><input type="radio" name="cmp-choice" checked={choice === s.id} onChange={() => setChoice(s.id)} /> {s.label}</label>
            ))}
            <label className="row"><input type="radio" name="cmp-choice" checked={choice === null} onChange={() => setChoice(null)} /> Not sure</label>
          </fieldset>
        ) : <p>Both answers do something well. Your marks and reasons are what count here.</p>}
        <div className="row">
          <Button variant="primary" loading={busy} onClick={() => void send()}>Compare with the explanation</Button>
          <span className="subtle" role="status">{status}</span>
        </div>
        <InlineError error={error} />
        {!explanation && !result && (asking ? (
          <div className="banner banner--info stack-sm" role="group" aria-label="Show the explanation now?">
            <p>You can read the explanation before marking anything. Your reading will say it came after the explanation.</p>
            <span className="row">
              <Button size="sm" variant="primary" onClick={() => void revealNow()}>Show the explanation</Button>
              <Button size="sm" variant="ghost" onClick={() => setAsking(false)}>Not yet</Button>
            </span>
          </div>
        ) : <p><Button size="sm" variant="ghost" onClick={() => setAsking(true)}>Show the explanation now</Button></p>)}
      </section>

      {result && (
        <section className="card stack" aria-labelledby="cmp-result">
          <h2 className="section-title" id="cmp-result" tabIndex={-1}>Your reading and the explanation</h2>
          {result.current_version !== result.lesson_version && (
            <p className="banner banner--info">These samples have been edited since. This reading shows them, and the explanation, as they were when you sent it.</p>
          )}
          <p>{(result.feedback as unknown as ComparisonFeedback).choice_note}</p>
          <ol className="stack-sm cmp-results" aria-label="Your marks compared with the explanation">
            {(result.feedback as unknown as ComparisonFeedback).selections.map((s) => (
              <li key={`${s.sample}/${s.sentence}/${s.kind}`} className="card stack-sm">
                <p className="row"><strong>Answer {s.sample}</strong> <span>you marked a {s.kind}</span> <Badge tone={STATUS[s.status].tone}>{STATUS[s.status].text}</Badge></p>
                <blockquote className="cmp-quote">{s.quote}</blockquote>
                <p><strong>Your reason:</strong> <span className="cmp-text">{s.reason}</span></p>
                <p>{s.note}{s.explanation_why && <> <strong>Its reason:</strong> {s.explanation_why}</>}</p>
              </li>
            ))}
          </ol>
          <p className="subtle">{(result.feedback as unknown as ComparisonFeedback).method}{result.revealed_early ? " This reading was sent after the explanation was shown." : ""}</p>
        </section>
      )}

      {shownExplanation && (
        <section className="card stack-sm" aria-labelledby="cmp-explanation">
          <h2 className="section-title" id="cmp-explanation" tabIndex={-1}>The explanation</h2>
          <p>{shownExplanation.summary}</p>
          {Object.entries(shownExplanation.samples).map(([sid, n]) => (
            <div key={sid} className="stack-sm">
              <h3 className="review-minor">Answer {sid}{shownExplanation.preferred === sid ? " (the explanation's choice)" : ""}</h3>
              <ul className="mini-list">
                {n.strengths.map((e, i) => <li key={`s${i}`}><strong>Strength · {rubricLabel(e.criterion)}:</strong> {e.sentences.map((x) => <q key={x} className="cmp-quote-inline">{sentenceText(sid, x)}</q>)} {e.why}</li>)}
                {n.gaps.map((e, i) => <li key={`g${i}`}><strong>Gap · {rubricLabel(e.criterion)}:</strong> {e.sentences.map((x) => <q key={x} className="cmp-quote-inline">{sentenceText(sid, x)}</q>)} {e.why}</li>)}
              </ul>
              <p className="subtle"><strong>Not settled:</strong> {n.uncertain}</p>
            </div>
          ))}
          <p><strong>Other good answers:</strong> {shownExplanation.alternatives}</p>
          <p>Next: <Link to={lesson.next_step.to ?? "/drills"}>{lesson.next_step.label}</Link>. Nothing here changes your plan.</p>
        </section>
      )}

      {readings.data && readings.data.length > 0 && (
        <section className="card stack-sm" aria-labelledby="cmp-earlier">
          <h2 className="section-title" id="cmp-earlier">Your earlier readings</h2>
          <ul className="mini-list">
            {readings.data.map((r) => (
              <li key={r.id}>
                <button type="button" className="link-button" onClick={async () => { const full = await api.sampleReading(r.id).catch(() => null); if (full) { setResult(full); focusAfter.current = "cmp-result"; } }}>{formatDateTime(r.created_at)}</button>
                <span className="subtle"> · {r.selections} excerpt{r.selections === 1 ? "" : "s"}, {r.matches} matching the explanation{r.revealed_early ? " · after the explanation" : ""} · version {r.lesson_version}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
