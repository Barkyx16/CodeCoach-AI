import type { InterviewAnswer } from "@/api/types";

/** Rubric feedback on one written answer. `title` and `headingId` let several share a page. */
export function FeedbackCard({ answer, title = "Feedback", headingId = "feedback-title" }: {
  answer: InterviewAnswer; title?: string; headingId?: string;
}) {
  const tone = answer.score >= 85 ? "success" : answer.score >= 65 ? "info" : "warning";
  return (
    <section className="card stack feedback-card" aria-labelledby={headingId} role="region">
      <div className="feedback-card__head">
        <div>
          <h2 className="section-title" id={headingId}>{title}</h2>
          <p className="feedback-card__summary" role="status">{answer.summary}</p>
        </div>
        <div className={`score-pill score-pill--${tone}`} aria-label={`Score ${answer.score} out of 100, ${answer.rating}`}>
          <strong>{answer.score}</strong><span>{answer.rating}</span>
        </div>
      </div>
      <ul className="rubric-check" aria-label="What interviewers listen for">
        {answer.points.map((p) => (
          <li key={p.label} className={p.covered ? "is-covered" : "is-missing"}>
            <span aria-hidden="true">{p.covered ? "✓" : "○"}</span>
            <div>
              <strong>{p.label}</strong>
              <span className="visually-hidden">{p.covered ? " (covered)" : " (missing)"}</span>
              {!p.covered && <p className="subtle">{p.advice}</p>}
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
      <p className="subtle">Coach: {answer.coach}. It checks what your answer covers and how it's built, not whether every detail is right.</p>
    </section>
  );
}
