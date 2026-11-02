import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import type { Difficulty, InterviewAnswer, QuestionSummary } from "@/api/types";
import { Badge, DifficultyBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Icon } from "@/components/Icon";
import { InlineError } from "@/components/States";
import { titleCase } from "@/lib/format";
import { FeedbackCard } from "@/features/careers/FeedbackCard";
import { KIND_LABEL } from "@/features/careers/kinds";
import { usePracticeTrack } from "@/features/careers/practiceTrack";

import { countWords, pickRound } from "./round";

const LEVELS: Difficulty[] = ["easy", "medium", "hard"];

type Result = { question: QuestionSummary; answer: InterviewAnswer | null };

function formatClock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** Seconds since `since` changed, ticking once a second. */
function useElapsed(since: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (since === null) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [since]);
  return since === null ? 0 : Math.max(0, Math.floor((now - since) / 1000));
}

/**
 * A mock interview made of the user's own career questions: five questions, one at a time, each
 * scored as it is answered, then a summary. Every answer is saved like any practice answer.
 */
export function QuestionInterviewPage() {
  const { track, career } = usePracticeTrack();
  const qc = useQueryClient();
  const [level, setLevel] = useState<Difficulty>("easy");
  const [round, setRound] = useState<QuestionSummary[] | null>(null);
  const [results, setResults] = useState<Result[]>([]);
  const [draft, setDraft] = useState("");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const elapsed = useElapsed(startedAt);
  const promptRef = useRef<HTMLHeadingElement>(null);
  const role = career?.title ?? titleCase(track);

  const start = useMutation({
    mutationFn: async () => (await api.questions(track, { difficulty: level, page: 1, page_size: 200 })).items,
    onSuccess: (pool) => {
      setRound(pickRound(pool));
      setResults([]);
      setDraft("");
      setStartedAt(Date.now());
    },
  });
  const answer = useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) => api.answerQuestion(track, id, text),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["careers", track] }),
  });

  const current = round && results.length < round.length ? round[results.length] : null;
  useEffect(() => { if (current) promptRef.current?.focus(); }, [current]);

  function next(result: Result) {
    setResults((r) => [...r, result]);
    setDraft("");
    setStartedAt(Date.now());
    answer.reset();
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!current) return;
    const saved = await answer.mutateAsync({ id: current.id, text: draft.trim() }).catch(() => null);
    if (saved) next({ question: current, answer: saved });
  }

  if (!round) {
    return (
      <div className="page interview-start">
        <div className="page__header">
          <div>
            <p className="eyebrow">MOCK INTERVIEW</p>
            <h1 className="page__title">{role} interview</h1>
            <p className="page__subtitle">Five questions from {role} interviews, one at a time, the way an interviewer would ask them.</p>
          </div>
        </div>
        <div className="interview-start__grid">
          <Card className="stack">
            <p className="interview-start__lead">How it works</p>
            <ol className="mini-list mini-list--numbered">
              <li>Why this job, what you know, a scenario, a time you did it, and leading others.</li>
              <li>Answer each one as you would out loud. Aim for 2-3 minutes and 120-350 words.</li>
              <li>Each answer is scored when you submit it, and saved to your practice.</li>
              <li>At the end you get every score, what you covered and what to add.</li>
            </ol>
          </Card>
          <form className="card stack" onSubmit={(e) => { e.preventDefault(); start.mutate(); }} aria-labelledby="round-setup">
            <h2 className="section-title" id="round-setup">Set up your interview</h2>
            <fieldset className="field">
              <legend className="field__label">Difficulty</legend>
              <div className="segmented">
                {LEVELS.map((l) => (
                  <label key={l} className={`segmented__option${level === l ? " segmented__option--active" : ""}`}>
                    <input type="radio" name="level" value={l} checked={level === l} onChange={() => setLevel(l)} />
                    {titleCase(l)}
                  </label>
                ))}
              </div>
            </fieldset>
            <InlineError error={start.error} />
            <Button type="submit" variant="primary" loading={start.isPending}>Start interview</Button>
            <p className="subtle">Want to work on one question at a time? <Link to="/problems?view=questions">Browse all {role} questions</Link>.</p>
          </form>
        </div>
      </div>
    );
  }

  if (round.length === 0) {
    return <div className="page"><p>No questions at this level yet.</p><Button onClick={() => setRound(null)}>Back</Button></div>;
  }

  if (current) {
    const words = countWords(draft);
    const n = results.length + 1;
    return (
      <div className="page question-page">
        <div className="page__header">
          <div>
            <p className="eyebrow">{role.toUpperCase()} INTERVIEW · QUESTION {n} OF {round.length}</p>
            <h1 className="page__title" ref={promptRef} tabIndex={-1}>{current.title}</h1>
            <p className="row question-page__meta">
              <DifficultyBadge difficulty={current.difficulty as Difficulty} />
              <Badge>{KIND_LABEL[current.kind] ?? titleCase(current.kind)}</Badge>
              <span className="subtle" aria-live="off"><Icon name="clock" size={14} /> {formatClock(elapsed)}</span>
            </p>
          </div>
        </div>
        <progress className="round-progress" max={round.length} value={results.length} aria-label={`Question ${n} of ${round.length}`} />
        <Card className="question-page__prompt">
          <h2 className="visually-hidden">The question</h2>
          <p>{current.prompt}</p>
        </Card>
        <form className="card stack" onSubmit={onSubmit}>
          <h2 className="section-title" id="round-answer-title">Your answer</h2>
          <textarea id="round-answer" aria-labelledby="round-answer-title" className="input answer-input" rows={10} maxLength={6000} value={draft}
            placeholder="Answer the way you'd say it in the interview…" aria-describedby="round-answer-count"
            onChange={(e) => setDraft(e.target.value)} />
          <div className="answer-actions">
            <span id="round-answer-count" className="subtle">{words} {words === 1 ? "word" : "words"} · aim for 120-350{elapsed > 180 ? " · past 3 minutes, start wrapping up" : ""}</span>
            <span className="row">
              <Button type="button" variant="ghost" onClick={() => next({ question: current, answer: null })}>Skip</Button>
              <Button type="submit" variant="primary" loading={answer.isPending} disabled={!draft.trim()}>
                {n === round.length ? "Finish interview" : "Next question"}
              </Button>
            </span>
          </div>
          <InlineError error={answer.error} />
        </form>
      </div>
    );
  }

  const scored = results.filter((r) => r.answer);
  const average = scored.length ? Math.round(scored.reduce((sum, r) => sum + r.answer!.score, 0) / scored.length) : null;
  const missed = new Map<string, number>();
  for (const r of scored) for (const p of r.answer!.points) if (!p.covered) missed.set(p.label, (missed.get(p.label) ?? 0) + 1);
  const focus = [...missed.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([label]) => label);

  return (
    <div className="page interview-summary">
      <div className="page__header">
        <div>
          <p className="eyebrow">MOCK INTERVIEW COMPLETE</p>
          <h1 className="page__title">{role} interview results</h1>
          <p className="page__subtitle">
            {average === null ? "You skipped every question." : `Average score ${average}/100 across ${scored.length} of ${round.length} answers.`}
          </p>
        </div>
        <div className="row dashboard__actions">
          <Link to="/dashboard" className="btn btn--secondary btn--md">Dashboard</Link>
          <Button variant="primary" onClick={() => start.mutate()} loading={start.isPending}>New interview</Button>
        </div>
      </div>
      {focus.length > 0 && (
        <Card className="stack">
          <h2 className="section-title">Work on next</h2>
          <ul className="mini-list">{focus.map((label) => <li key={label}>{label}</li>)}</ul>
        </Card>
      )}
      <ol className="round-results">
        {results.map((r, i) => (
          <li key={r.question.id}>
            <details className="card round-result" open={i === 0}>
              <summary>
                <span className="round-result__n">{i + 1}</span>
                <strong>{r.question.title}</strong>
                <Badge>{KIND_LABEL[r.question.kind] ?? titleCase(r.question.kind)}</Badge>
                <span className="round-result__score">{r.answer ? `${r.answer.score}/100 · ${r.answer.rating}` : "Skipped"}</span>
              </summary>
              <div className="stack round-result__body">
                <p className="subtle">{r.question.prompt}</p>
                {r.answer
                  ? <FeedbackCard answer={r.answer} title="Feedback" headingId={`round-feedback-${i}`} />
                  : <p><Link to={`/careers/${track}/questions/${r.question.id}`}>Answer this question on its own</Link></p>}
              </div>
            </details>
          </li>
        ))}
      </ol>
    </div>
  );
}
