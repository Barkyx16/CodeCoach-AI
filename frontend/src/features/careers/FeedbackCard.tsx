import { useId, useRef, useState } from "react";

import type { InterviewAnswer } from "@/api/types";
import { FeedbackKind } from "@/components/FeedbackKind";
import { ReportIssue } from "@/features/content/ReportIssue";

import { AnsweredVersion } from "./AnsweredVersion";

type Point = InterviewAnswer["points"][number];

/** A checked quote's place in the answer: [start, end) in UTF-16 code units, as JavaScript indexes. */
function placeOf(answer: string, p: Point): [number, number] | null {
  if (p.evidence_status !== "verified" || !p.span || p.span.length !== 2) return null;
  const [start, end] = p.span;
  if (start === undefined || end === undefined) return null;
  return 0 <= start && start < end && end <= answer.length ? [start, end] : null;
}

/** The answer as it was reviewed, with one quote marked. */
function AnswerWithQuote({ text, place, markId }: { text: string; place: [number, number] | null; markId: string }) {
  if (!place) return <p className="feedback-card__answer-text">{text}</p>;
  const [start, end] = place;
  return (
    <p className="feedback-card__answer-text">
      {text.slice(0, start)}
      <mark id={markId} tabIndex={-1}>{text.slice(start, end)}</mark>
      {text.slice(end)}
    </p>
  );
}

/** Rubric feedback on one written answer. `title` and `headingId` let several share a page. */
export function FeedbackCard({ answer, title = "Feedback", headingId = "feedback-title", track, draft }: {
  answer: InterviewAnswer; title?: string; headingId?: string;
  /** The answer's career: enables "Report a problem with this feedback" and version notes. */
  track?: string;
  /** What's in the answer box now: if it differs from the reviewed answer, the card says so. */
  draft?: string;
}) {
  const tone = answer.score >= 85 ? "success" : answer.score >= 65 ? "info" : "warning";
  const insufficient = answer.evidence_level === "insufficient";
  const uid = useId();
  const answerId = `${uid}-answer`;
  const markId = `${uid}-quote`;
  const [shown, setShown] = useState<{ open: boolean; point: string | null }>({ open: false, point: null });
  const panel = useRef<HTMLDivElement>(null);
  const shownPlace = shown.point ? placeOf(answer.answer, answer.points.find((p) => p.label === shown.point)!) : null;
  const changed = !!draft?.trim() && draft.trim() !== answer.answer.trim();

  function showIn(label: string) {
    setShown({ open: true, point: label });
    // after it renders: bring the marked words into view and give them focus, so keyboard and
    // screen-reader users land on them too
    window.setTimeout(() => {
      const mark = document.getElementById(markId);
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      mark?.scrollIntoView?.({ block: "center", behavior: reduce ? "auto" : "smooth" });
      (mark ?? panel.current)?.focus({ preventScroll: true });
    }, 0);
  }

  return (
    <section className="card stack feedback-card" aria-labelledby={headingId} role="region">
      <div className="feedback-card__head">
        <div>
          <h2 className="section-title" id={headingId} tabIndex={-1}>{title}</h2>
          <p className="feedback-card__summary" role="status">{answer.summary}</p>
        </div>
        {insufficient ? (
          // Too short to evaluate: no precise number is shown, because there isn't evidence for one.
          <div className="score-pill score-pill--neutral" aria-label="Not enough to score yet">
            <strong aria-hidden="true">—</strong><span>Not enough to score</span>
          </div>
        ) : (
          <div className={`score-pill score-pill--${tone}`} aria-label={`Score ${answer.score} out of 100, ${answer.rating}`}>
            <strong>{answer.score}</strong><span>{answer.rating}</span>
          </div>
        )}
      </div>
      <FeedbackKind kind="structure" />
      {answer.evaluation_note && (
        <p className={answer.evaluation_status === "measured" ? "subtle" : "banner banner--info"}>{answer.evaluation_note}</p>
      )}
      {changed && (
        <p className="banner banner--info" role="note">
          You've changed your answer since. This feedback is for the version you sent; send the new one to get feedback on it.
        </p>
      )}
      <ul className="rubric-check" aria-label="What interviewers listen for">
        {answer.points.map((p) => (
          <li key={p.label} className={p.covered ? "is-covered" : "is-missing"}>
            <span aria-hidden="true">{p.covered ? "✓" : "○"}</span>
            <div>
              <strong>{p.label}</strong>
              <span className="visually-hidden">{p.covered ? " (covered)" : " (missing)"}</span>
              {!p.covered && <p className="subtle">{p.advice}</p>}
              {p.scope_note && <p className="subtle feedback-card__scope">{p.scope_note}</p>}
              {p.covered && <Evidence point={p} place={placeOf(answer.answer, p)} onShow={() => showIn(p.label)} controls={answerId} />}
            </div>
          </li>
        ))}
      </ul>
      <details className="feedback-card__answer" open={shown.open}
        onToggle={(e) => { const open = (e.currentTarget as HTMLDetailsElement).open; if (open !== shown.open) setShown((s) => ({ ...s, open })); }}>
        <summary>The answer this feedback is for</summary>
        <div id={answerId} ref={panel} tabIndex={-1}>
          {/* only while open: pages that show the answer beside its feedback don't repeat it */}
          {shown.open && <AnswerWithQuote text={answer.answer} place={shownPlace} markId={markId} />}
          {shown.open && shown.point && shownPlace && <p className="subtle">Marked: where “{shown.point}” was found.</p>}
        </div>
      </details>
      {answer.notes.length > 0 && (
        <div className="stack feedback-card__notes">
          <h3 className="section-title">Delivery</h3>
          <ul className="mini-list">{answer.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </div>
      )}
      <div className="stack">
        <h3 className="section-title">A strong answer includes</h3>
        <ol className="mini-list mini-list--numbered">{answer.outline.map((line) => <li key={line}>{line}</li>)}</ol>
      </div>
      <p className="subtle">
        Coach: {answer.coach}, rubric {answer.rubric_version}. It looks for each point in your words (the quotes above are where it found them) and
        applies fixed checks like length; it doesn't judge whether every detail is right, and it isn't an employer's rubric.
      </p>
      {track && <AnsweredVersion track={track} questionId={answer.question_id} version={answer.content_version} />}
      {track && (
        <ReportIssue type="question" id={`${track}/${answer.question_id}`} version={answer.content_version}
          context="feedback" answerId={answer.id} excerptSource={answer.answer} />
      )}
    </section>
  );
}

/** The evidence for a covered point: a checked quote that can be found in the answer, an older
 * quote whose place wasn't recorded, or a note that a quote couldn't be checked (nothing is made up). */
function Evidence({ point, place, onShow, controls }: { point: Point; place: [number, number] | null; onShow: () => void; controls: string }) {
  if (point.evidence_status === "omitted") {
    return <p className="feedback-card__evidence subtle">Found in your answer, but the quote couldn't be checked against it, so it isn't shown.</p>;
  }
  if (!point.evidence) return null;
  return (
    <div className="feedback-card__evidence">
      <p>
        <span className="subtle">{place ? "From your answer: " : "From your answer (older feedback: where it was isn't recorded): "}</span>
        “{point.evidence}”
      </p>
      {place && (
        <button type="button" className="link-button" aria-controls={controls} onClick={onShow}>
          Show it in your answer<span className="visually-hidden">: {point.label}</span>
        </button>
      )}
    </div>
  );
}

