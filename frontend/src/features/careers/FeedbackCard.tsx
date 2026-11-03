import type { InterviewAnswer } from "@/api/types";
import { ReportIssue } from "@/features/content/ReportIssue";

import { AnsweredVersion } from "./AnsweredVersion";

/** Rubric feedback on one written answer. `title` and `headingId` let several share a page. */
export function FeedbackCard({ answer, title = "Feedback", headingId = "feedback-title", track }: {
  answer: InterviewAnswer; title?: string; headingId?: string;
  /** The answer's career: enables "Report a problem with this feedback" and version notes. */
  track?: string;
}) {
  const tone = answer.score >= 85 ? "success" : answer.score >= 65 ? "info" : "warning";
  const insufficient = answer.evidence_level === "insufficient";
  return (
    <section className="card stack feedback-card" aria-labelledby={headingId} role="region">
      <div className="feedback-card__head">
        <div>
          <h2 className="section-title" id={headingId}>{title}</h2>
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
      <ul className="rubric-check" aria-label="What interviewers listen for">
        {answer.points.map((p) => (
          <li key={p.label} className={p.covered ? "is-covered" : "is-missing"}>
            <span aria-hidden="true">{p.covered ? "✓" : "○"}</span>
            <div>
              <strong>{p.label}</strong>
              <span className="visually-hidden">{p.covered ? " (covered)" : " (missing)"}</span>
              {!p.covered && <p className="subtle">{p.advice}</p>}
              {p.covered && p.evidence && <p className="feedback-card__evidence"><span className="subtle">From your answer: </span>“{p.evidence}”</p>}
            </div>
          </li>
        ))}
      </ul>
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
