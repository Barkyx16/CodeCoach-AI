import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { useAnswerQuestion, useMyAnswers, useQuestion } from "@/api/queries";
import type { Difficulty, InterviewAnswer } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Badge, DifficultyBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Icon } from "@/components/Icon";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { timeAgo } from "@/lib/format";

import { KIND_LABEL } from "./kinds";

const MAX_CHARS = 6000;

function countWords(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

/** One interview question: read it, write an answer, get rubric feedback, compare with past tries. */
export function QuestionPage() {
  const { track = "", id = "" } = useParams();
  const { isAuthenticated, user, continueAsGuest } = useAuth();
  const question = useQuestion(track, id);
  const answers = useMyAnswers(track, id, isAuthenticated);
  const submit = useAnswerQuestion(track, id);
  const [draft, setDraft] = useState("");
  const [latest, setLatest] = useState<InterviewAnswer | null>(null);
  const [guestError, setGuestError] = useState<unknown>(null);

  if (question.isPending) return <LoadingState label="Loading question…" />;
  if (question.isError) {
    return <div className="page"><ErrorState error={question.error} onRetry={() => question.refetch()} /></div>;
  }
  const q = question.data;
  const words = countWords(draft);
  const backTo = user?.career_track === track ? "/problems?view=questions" : `/problems?career=${track}&view=questions`;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const result = await submit.mutateAsync(draft.trim()).catch(() => null);
    if (result) setLatest(result);
  }

  return (
    <div className="page question-page">
      <nav className="question-page__crumbs" aria-label="Breadcrumb">
        <Link to={backTo}><Icon name="book" size={15} />{q.career_title} questions</Link>
      </nav>
      <div className="page__header">
        <div>
          <p className="eyebrow">{(KIND_LABEL[q.kind] ?? q.kind).toUpperCase()} QUESTION</p>
          <h1 className="page__title">{q.title}</h1>
          <p className="row question-page__meta">
            <DifficultyBadge difficulty={q.difficulty as Difficulty} />
            <Badge>{KIND_LABEL[q.kind] ?? q.kind}</Badge>
            {q.best_score !== null && q.best_score !== undefined && <Badge tone="success">Best score {q.best_score}</Badge>}
          </p>
        </div>
      </div>

      <div className="question-page__layout">
        <div className="stack">
          <Card className="question-page__prompt">
            <h2 className="visually-hidden">The question</h2>
            <p>{q.prompt}</p>
          </Card>

          <form className="card stack" onSubmit={onSubmit} aria-labelledby="answer-title">
            <h2 className="section-title" id="answer-title">Write your answer</h2>
            <label className="visually-hidden" htmlFor="answer-text">Your answer</label>
            <textarea id="answer-text" className="input answer-input" rows={10} maxLength={MAX_CHARS} value={draft}
              placeholder="Write it the way you'd say it in the interview…"
              aria-describedby="answer-count" onChange={(e) => setDraft(e.target.value)} />
            <div className="answer-actions">
              <span id="answer-count" className="subtle">{words} {words === 1 ? "word" : "words"} · aim for 120-350</span>
              {isAuthenticated ? (
                <Button type="submit" variant="primary" loading={submit.isPending} disabled={!draft.trim()}>
                  Get feedback
                </Button>
              ) : (
                <span className="row">
                  <Link className="btn btn--secondary btn--md" to="/login" state={{ from: `/careers/${track}/questions/${id}` }}>Sign in</Link>
                  <Button variant="primary" onClick={() => { setGuestError(null); continueAsGuest(undefined, track).catch(setGuestError); }}>
                    Try as a guest
                  </Button>
                </span>
              )}
            </div>
            {!isAuthenticated && <p className="subtle">Feedback needs an account so your answers are saved. A guest session takes one click.</p>}
            <InlineError error={submit.error ?? guestError} />
          </form>

          {latest && <FeedbackCard answer={latest} />}
        </div>

        <aside className="stack">
          <Card className="stack">
            <h2 className="section-title"><Icon name="spark" size={16} />Tips</h2>
            <ul className="mini-list">{q.tips.map((t) => <li key={t}>{t}</li>)}</ul>
          </Card>
          {isAuthenticated && answers.data && answers.data.length > 0 && (
            <Card className="stack">
              <h2 className="section-title">Your past answers</h2>
              <ul className="past-answers">
                {answers.data.map((a) => (
                  <li key={a.id}>
                    <button type="button" className="past-answers__item" onClick={() => setLatest(a)}
                      aria-pressed={latest?.id === a.id}>
                      <span>{a.rating}</span>
                      <span className="subtle">{a.score}/100 · {timeAgo(a.created_at)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}

function FeedbackCard({ answer }: { answer: InterviewAnswer }) {
  const tone = answer.score >= 85 ? "success" : answer.score >= 65 ? "info" : "warning";
  return (
    <section className="card stack feedback-card" aria-labelledby="feedback-title" role="region">
      <div className="feedback-card__head">
        <div>
          <h2 className="section-title" id="feedback-title">Feedback</h2>
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
