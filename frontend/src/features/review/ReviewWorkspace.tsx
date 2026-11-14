import { useEffect, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useInterviewReview, useReviewQueueMutation } from "@/api/queries";
import type { Interview, InterviewReview, ReviewEntry } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { PrivateUnavailable } from "@/components/Unavailable";
import { isGone } from "@/lib/errors";
import { readStoredDraft } from "@/hooks/useStoredDraft";
import { diag } from "@/lib/diagnostics";
import { formatDateTime, titleCase } from "@/lib/format";
import { FeedbackCard } from "@/features/careers/FeedbackCard";
import { KIND_LABEL } from "@/features/careers/kinds";
import { OVERALL_LABELS } from "@/features/interview/phases";
import { RubricChart } from "@/features/interview/RubricChart";
import { screenChanged } from "@/features/interview/roundDiag";
import { roundDraftKey } from "@/features/interview/roundDrafts";
import { EngagementNote } from "@/features/voice/EngagementMeter";
import { NoteCapture } from "@/features/notes/NoteCapture";
import { AcceptImprovement } from "@/features/actions/AcceptImprovement";

const STATUS_TEXT: Record<ReviewEntry["status"], string> = {
  answered: "Answered", skipped: "Skipped", not_reached: "Not reached", said: "",
};
const DIM_STATUS: Record<string, string> = { evaluated: "Evaluated", not_evaluated: "Not evaluated", not_applicable: "Not applicable" };

function minutes(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "unknown";
  const m = Math.round(seconds / 60);
  return m < 1 ? "under a minute" : `${m} min`;
}

/** The post-interview review for both interview kinds: summary, focus, timeline and detail. */
export function ReviewWorkspace({ iv }: { iv: Interview }) {
  const review = useInterviewReview(iv.id);
  const state = review.isPending ? "loading" : review.isError ? "error" : "ready";
  useEffect(() => {
    diag("review_view", { interviewId: iv.id, status: iv.status, state });
    screenChanged(iv.id, `results:${state}`); // the round's last action is on screen
  }, [iv.id, iv.status, state]);
  if (review.isPending) return <LoadingState label="Loading your review…" />;
  if (review.isError && isGone(review.error)) return <PrivateUnavailable what="interview" list={ALL_INTERVIEWS} />;
  if (review.isError) return <div className="page"><BackLink fallback={ALL_INTERVIEWS} /><ErrorState error={review.error} onRetry={() => void review.refetch()} /></div>;
  return <Review iv={iv} r={review.data} />;
}

/** Opened directly (a bookmark, a new tab, the link in History's export): somewhere useful. */
const ALL_INTERVIEWS = { to: "/history?type=interview", label: "All your interviews" };

function Review({ iv, r }: { iv: Interview; r: InterviewReview }) {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const [showAll, setShowAll] = useState(false);
  const items = r.items;
  const selectedKey = params.get("item") ?? items[0]?.key ?? "";
  const selected = items.find((i) => i.key === selectedKey) ?? items[0];
  const select = (key: string, label = "") => {
    const next = new URLSearchParams(params);
    next.set("item", key);
    const line = key === "code" ? /Line (\d+)/.exec(label)?.[1] : undefined;
    if (line) next.set("line", line);
    else next.delete("line");
    // Keep where this page was opened from: choosing an item mustn't drop "Back to History".
    setParams(next, { replace: true, state: location.state });
    if (key === "code") document.getElementById("review-code")?.scrollIntoView?.({ block: "start" });
    else document.getElementById("review-detail")?.focus();
  };
  const at = selected ? items.indexOf(selected) : 0;
  const answered = items.filter((i) => i.feedback);
  const scores = answered.map((i) => i.feedback!.score);
  const isRound = r.kind === "questions";
  const role = r.career_title ?? titleCase(r.track ?? "");
  const ev = iv.evaluation;
  const overall = ev ? OVERALL_LABELS[ev.overall] : null;

  return (
    <div className="page review">
      <BackLink fallback={ALL_INTERVIEWS} />
      <div className="page__header">
        <div>
          <p className="eyebrow">{isRound ? "MOCK INTERVIEW" : "CODING INTERVIEW"} · {r.status_label.toUpperCase()}</p>
          <h1 className="page__title">{isRound ? `${role} interview results` : "Interview feedback"}</h1>
          <p className="page__subtitle">
            {isRound
              ? (scores.length
                ? `Average score ${Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)}/100 across ${answered.length} of ${items.length} answers.`
                : "No questions were answered, so there are no scores.")
                + (items.some((i) => i.status === "skipped") ? ` ${items.filter((i) => i.status === "skipped").length} skipped.` : "")
                + (items.some((i) => i.status === "not_reached") ? ` ${items.filter((i) => i.status === "not_reached").length} not reached.` : "")
              : `${r.problem?.title ?? "Coding problem"} · ${r.status_label}`}
          </p>
          <p className="subtle review__meta">Started {formatDateTime(r.started_at)} · took {minutes(r.elapsed_seconds)} of {minutes(r.time_limit_seconds)}</p>
        </div>
        <div className="row dashboard__actions">
          <Link to="/dashboard" className="btn btn--secondary btn--md">Dashboard</Link>
          {isRound
            ? <Link to="/interviews/questions" className="btn btn--primary btn--md">New interview</Link>
            : <>
              <Link to="/interviews" className="btn btn--primary btn--md">Start another</Link>
              {r.problem && <Link to={`/problems/${r.problem.slug}`} className="btn btn--secondary btn--md">Practice this problem</Link>}
            </>}
        </div>
      </div>

      {r.notices.length > 0 && (
        <div className={`banner ${r.completed ? "banner--info" : "banner--warning"}`} role="status">
          <ul className="mini-list review__notices">{r.notices.map((n) => <li key={n}>{n}</li>)}</ul>
        </div>
      )}

      <div className="review__layout">
        <div className="stack">
          {r.improvements.length > 0 && (
            <Card className="stack">
              <h2 className="section-title">Work on next</h2>
              <ol className="review__improvements">
                {r.improvements.map((imp) => (
                  <li key={imp.key || imp.title} className="stack">
                    <strong>{imp.title}</strong>
                    <p className="subtle">{imp.why}</p>
                    {imp.evidence.length > 0 && (
                      <p className="review__evidence">
                        <span className="activity-card__label">Seen in:</span>{" "}
                        {imp.evidence.map((e) => e.item_key
                          ? <button key={e.item_key + e.label} type="button" className="evidence-link" onClick={() => select(e.item_key, e.label)}>{e.label}{e.excerpt ? `: “${e.excerpt}”` : ""}</button>
                          : <span key={e.label} className="subtle">{e.label}</span>)}
                      </p>
                    )}
                    {imp.practice.retry_index !== null && imp.practice.retry_index !== undefined
                      ? <Link className="btn btn--secondary btn--sm review__practice" to={`/interviews/${r.id}/retry/${imp.practice.retry_index}`}>{imp.practice.label}</Link>
                      : imp.practice.href && <Link className="btn btn--secondary btn--sm review__practice" to={imp.practice.href}>{imp.practice.label}</Link>}
                    <AcceptImprovement interviewId={r.id} improvementKey={imp.key} actionId={imp.action_id} title={imp.title} />
                  </li>
                ))}
              </ol>
            </Card>
          )}

          {!isRound && ev && (
            <Card className="stack">
              <div className="row"><h2 className="section-title">Overall</h2>{overall && <Badge tone={overall.tone}>{overall.label}</Badge>}</div>
              <p className="interview-results__summary">{ev.summary}</p>
              <RubricChart scores={ev.scores} />
            </Card>
          )}
          <Card className="stack">
            <h2 className="section-title">How it was assessed</h2>
            <ul className="review__dims">
              {r.overall.map((d) => <DimensionRow key={d.name} d={d} onEvidence={select} />)}
            </ul>
            <p className="subtle">{r.disclaimer}</p>
          </Card>
          {(r.perspectives ?? []).length > 0 && (
            <Card className="stack" role="region" aria-labelledby="perspectives-title">
              <h2 className="section-title" id="perspectives-title">Panel perspectives (simulated)</h2>
              <p className="subtle">The same rubric, split by which simulated role asked. Not separate human judgments.</p>
              <ul className="perspectives">
                {(r.perspectives ?? []).map((p) => (
                  <li key={p.role.id} className="card stack-sm">
                    <strong>{p.role.title}</strong>
                    <span className="subtle">{p.summary}</span>
                    <span>{p.average_score !== null && p.average_score !== undefined ? `${p.average_score}/100 average` : "No answers"} · {p.answered} of {p.asked} answered</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        <section className="stack" aria-labelledby="timeline-title">
          <div className="section-heading">
            <h2 className="section-title" id="timeline-title">{isRound ? "Questions" : "Transcript"}</h2>
            <Button size="sm" variant="ghost" aria-pressed={showAll} onClick={() => setShowAll((v) => !v)}>{showAll ? "One at a time" : "Show all"}</Button>
          </div>
          <ol className="review__timeline">
            {items.map((i, n) => (
              <li key={i.key}>
                <button type="button" className={`timeline-item${i === selected ? " is-selected" : ""}`} aria-current={i === selected ? "true" : undefined} onClick={() => select(i.key)}>
                  <span className="timeline-item__n">{n + 1}</span>
                  <span className="timeline-item__title">{i.speaker ? `${i.speaker.title}: ` : ""}{i.title}</span>
                  <span className="subtle timeline-item__status">
                    {isRound ? (i.feedback ? `${i.feedback.score}/100 · ${i.feedback.rating}` : STATUS_TEXT[i.status]) : i.asked_at ? new Date(i.asked_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : ""}
                  </span>
                </button>
              </li>
            ))}
            {r.final_code && <li><button type="button" className={`timeline-item${selectedKey === "code" ? " is-selected" : ""}`} onClick={() => select("code")}><span className="timeline-item__n">{"{}"}</span><span className="timeline-item__title">Your final code</span></button></li>}
          </ol>
          {showAll
            ? items.map((i) => <Detail key={i.key} r={r} item={i} />)
            : selected && selectedKey !== "code" && (
              <>
                <Detail r={r} item={selected} focusable />
                <div className="row review__nav">
                  <Button size="sm" variant="ghost" disabled={at <= 0} onClick={() => select(items[at - 1]!.key)}>Previous</Button>
                  <span className="subtle">{at + 1} of {items.length}</span>
                  <Button size="sm" variant="ghost" disabled={at >= items.length - 1} onClick={() => select(items[at + 1]!.key)}>Next</Button>
                </div>
              </>
            )}
          {r.final_code && (selectedKey === "code" || showAll) && <CodeView code={r.final_code} highlight={codeLine(r, params.get("line"))} />}
        </section>
      </div>
    </div>
  );
}

function codeLine(_r: InterviewReview, line: string | null): number | null {
  return line ? Number(line) || null : null;
}


function DimensionRow({ d, onEvidence }: { d: InterviewReview["overall"][number]; onEvidence: (key: string, label: string) => void }) {
  const points = d.points ?? [];
  const evidence = d.evidence ?? [];
  return (
    <li className={`review-dim review-dim--${d.status}`}>
      <div className="review-dim__head"><strong>{d.name}</strong><span className="subtle">{DIM_STATUS[d.status]}</span></div>
      <p>{d.summary}</p>
      {points.length > 0 && <ul className="mini-list">{points.map((p) => <li key={p}>{p}</li>)}</ul>}
      {evidence.length > 0 && (
        <p className="review__evidence">
          {evidence.map((e) => e.item_key
            ? <button key={e.label + (e.excerpt ?? "")} type="button" className="evidence-link" onClick={() => onEvidence(e.item_key, e.label)}>{e.label}{e.excerpt ? `: “${e.excerpt}”` : ""}</button>
            : <span key={e.label} className="subtle">{e.label}</span>)}
        </p>
      )}
    </li>
  );
}

function Detail({ r, item, focusable = false }: { r: InterviewReview; item: ReviewEntry; focusable?: boolean }) {
  const location = useLocation();
  const save = useReviewQueueMutation(() => api.addReview({ track: r.track ?? "", question_id: item.question_id ?? "", session_id: r.id }));
  const isRound = r.kind === "questions";
  const draft = isRound && !item.feedback ? readStoredDraft(roundDraftKey(r.id, item.index)) : "";
  const saved = item.in_review_queue || save.isSuccess;
  return (
    <article id={focusable ? "review-detail" : undefined} tabIndex={focusable ? -1 : undefined} className="card stack review-detail" aria-labelledby={`detail-${item.key}`}>
      <div className="review-detail__head">
        <h3 className="section-title" id={`detail-${item.key}`}>{isRound ? `${item.index + 1}. ${item.title}` : item.title}</h3>
        {isRound && <Badge>{KIND_LABEL[item.kind] ?? titleCase(item.kind)}</Badge>}
      </div>
      {item.speaker && <p className="speaker-label">Asked by the {item.speaker.title.toLowerCase()} (simulated role)</p>}
      {isRound && <p className="question-page__prompt-text">{item.prompt}</p>}
      {item.asked_at && <p className="subtle review-detail__time">{isRound ? "Asked" : "Said"} {formatDateTime(item.asked_at)}{item.answered_at ? ` · answered ${formatDateTime(item.answered_at)}` : ""}</p>}
      {!isRound && <blockquote className="round-result__answer">{item.prompt}</blockquote>}
      {isRound && (item.answer_text
        ? <blockquote className="round-result__answer">{item.answer_text}</blockquote>
        : <p className="banner banner--info">{item.status === "skipped" ? "Skipped" : "Not reached"}: no answer, so no feedback.</p>)}
      {item.followup && item.followup.status !== "pending" && (
        <div className="review-followup stack-sm">
          <p><span className="speaker-label">Follow-up{item.followup.speaker ? ` from the ${item.followup.speaker.title.toLowerCase()}` : ""}:</span> {item.followup.question}</p>
          {item.followup.status === "skipped"
            ? <p className="subtle">You skipped this follow-up.</p>
            : <>
                <blockquote className="round-result__answer">{item.followup.answer}</blockquote>
                <p className="subtle">{item.followup.covered ? `Your reply gave the ${item.followup.detail} it asked for.` : `Your reply didn't clearly give the ${item.followup.detail} it asked for.`} (A simple check, not a score.)</p>
              </>}
        </div>
      )}
      {item.transcription_note && <p className="subtle">{item.transcription_note}</p>}
      {item.engagement && <EngagementNote engagement={item.engagement} />}
      {item.dimensions.length > 0 && (
        <details className="review-detail__dims">
          <summary>How this answer was assessed</summary>
          <ul className="review__dims">{item.dimensions.map((d) => <DimensionRow key={d.name} d={d} onEvidence={() => undefined} />)}</ul>
        </details>
      )}
      {item.feedback && (
        <details className="review-detail__feedback">
          <summary>Full feedback and a strong-answer outline</summary>
          <FeedbackCard answer={item.feedback} title="Feedback" headingId={`fb-${item.key}`} track={r.track ?? undefined} />
        </details>
      )}
      {isRound && (
        <div className="row review-detail__actions">
          <Link className="btn btn--primary btn--sm" to={`/interviews/${r.id}/retry/${item.index}`} state={{ from: location.pathname + location.search, fromLabel: "Back to the review" }}>
            {item.feedback ? "Retry this question" : "Answer this question"}
          </Link>
          {item.retries > 0 && <Link className="btn btn--secondary btn--sm" to={`/interviews/${r.id}/retry/${item.index}`}>Compare {item.retries} {item.retries === 1 ? "retry" : "retries"}</Link>}
          {item.feedback && (
            <Link className="btn btn--ghost btn--sm" to={`/share/new?answer=${encodeURIComponent(item.feedback.id)}`}
              state={{ from: location.pathname + location.search, fromLabel: "Back to the review" }}>Ask someone for feedback</Link>
          )}
          {saved ? <span className="subtle">In your review queue</span>
            : <Button size="sm" variant="ghost" loading={save.isPending} onClick={() => save.mutate(undefined)}>Save for later review</Button>}
          {draft && (
            <Link to={`/careers/${r.track}/questions/${item.question_id}`} state={{ draft }}>Finish your saved draft on its own page</Link>
          )}
        </div>
      )}
      <InlineError error={save.error} />
      {isRound && (
        <NoteCapture key={item.key} source={{ type: "interview", id: r.id, question_index: item.index }}
          excerpt={item.answer_text} excerptLabel="your answer" />
      )}
    </article>
  );
}

function CodeView({ code, highlight }: { code: string; highlight: number | null }) {
  return (
    <Card className="stack" >
      <h3 className="section-title" id="review-code">Your final code</h3>
      <pre className="review-code" tabIndex={0} aria-labelledby="review-code">
        {code.split("\n").map((line, i) => (
          <span key={i} className={`review-code__line${highlight === i + 1 ? " is-flagged" : ""}`}><span className="review-code__n" aria-hidden="true">{i + 1}</span>{line || " "}{"\n"}</span>
        ))}
      </pre>
      <p className="subtle">Interview code isn't run by the judge. To get a verdict, open the problem and submit it.</p>
    </Card>
  );
}
