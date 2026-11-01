import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useParams } from "react-router-dom";

import {
  queryKeys,
  useAbandonInterview,
  useFinishInterview,
  useInterview,
  useInterviewMessage,
  useProblem,
} from "@/api/queries";
import type { Interview } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Badge, DifficultyBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { CodeEditor } from "@/features/workspace/CodeEditor";
import { useDraft } from "@/features/workspace/useDraft";

import { PhaseStepper } from "./PhaseStepper";
import { OVERALL_LABELS } from "./phases";
import { RubricChart } from "./RubricChart";
import { Transcript } from "./Transcript";
import { formatClock, useCountdown } from "./useCountdown";
import { Icon } from "@/components/Icon";

export default function InterviewSessionPage() {
  const { id = "" } = useParams();
  const interview = useInterview(id);
  if (interview.isPending) return <LoadingState label="Loading interview…" />;
  if (interview.isError) return <div className="page"><ErrorState error={interview.error} onRetry={() => interview.refetch()} /></div>;
  return interview.data.status === "in_progress"
    ? <LiveInterview key={interview.data.id} iv={interview.data} />
    : <InterviewResults iv={interview.data} />;
}

function LiveInterview({ iv }: { iv: Interview }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const problem = useProblem(iv.problem.slug);
  const draft = useDraft(`interview-${iv.id}`, problem.data?.starter_code ?? "", user?.id ?? "anon");
  const send = useInterviewMessage(iv.id);
  const finish = useFinishInterview(iv.id);
  const abandon = useAbandonInterview(iv.id);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const seconds = useCountdown(iv.deadline_at, true);
  const ready = iv.phase === null; // interviewer wrapped up
  const busy = send.isPending || finish.isPending || abandon.isPending;
  const canSend = !ready && seconds > 0 && iv.candidate_turns_remaining > 0 && !!problem.data && !busy;

  // When the clock runs out, ask the server: it closes the interview and returns feedback.
  useEffect(() => {
    if (seconds === 0) void queryClient.invalidateQueries({ queryKey: queryKeys.interview(iv.id) });
  }, [seconds, iv.id, queryClient]);

  async function onSend(e?: FormEvent) {
    e?.preventDefault();
    const text = message.trim();
    if (!text || !canSend) return;
    setPending(text);
    setMessage("");
    try {
      await send.mutateAsync({ message: text, code: draft.code });
    } catch {
      setMessage(text); // give the text back so nothing is lost
    } finally {
      setPending(null);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      void onSend();
    }
  }

  const lowTime = seconds <= 120;
  return (
    <div className="interview">
      <header className="interview__bar">
        <div className="row">
          <h1 className="interview__title">{iv.problem.title}</h1>
          <DifficultyBadge difficulty={iv.problem.difficulty} />
          <Link to={`/problems/${iv.problem.slug}`} target="_blank" rel="noreferrer" className="subtle interview__statement-link">Problem statement <Icon name="arrow" size={14} /><span className="visually-hidden">(opens in a new tab)</span></Link>
        </div>
        <PhaseStepper phaseIndex={iv.phase_index} />
        <div className="row">
          <span className={`clock${lowTime ? " clock--low" : ""}`} role="timer" aria-label={`${formatClock(seconds)} remaining`}>
            <Icon name="clock" size={17} />
            {formatClock(seconds)}
          </span>
          <Button size="sm" variant="ghost" loading={abandon.isPending} disabled={busy}
            onClick={() => { if (window.confirm("End the interview now? You'll still get feedback.")) abandon.mutate(); }}>
            End early
          </Button>
          <Button size="sm" variant={ready ? "primary" : "secondary"} loading={finish.isPending} disabled={busy}
            onClick={() => finish.mutate(draft.code)}>
            Finish & get feedback
          </Button>
        </div>
      </header>

      <div className="interview__body">
        <section className="interview__chat" aria-label="Conversation">
          {iv.phase_guide && <p className="interview__guide subtle">Now: {iv.phase_guide}</p>}
          <Transcript turns={iv.turns} pending={pending} />
          <form className="composer" onSubmit={onSend}>
            <label className="visually-hidden" htmlFor="iv-message">Your answer</label>
            <textarea id="iv-message" className="input composer__input" rows={3} maxLength={4000}
              disabled={ready || seconds === 0 || iv.candidate_turns_remaining === 0 || finish.isPending || abandon.isPending}
              placeholder={ready ? "The interviewer has wrapped up. Click Finish to see your feedback." : "Think out loud… (Ctrl/⌘ + Enter to send)"}
              value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={onKeyDown} />
            <div className="composer__actions">
              <span className="subtle">{iv.candidate_turns_remaining} messages left</span>
              <Button type="submit" variant="primary" loading={send.isPending} disabled={!message.trim() || !canSend}>Send</Button>
            </div>
            <InlineError error={send.error ?? finish.error ?? abandon.error} />
          </form>
        </section>
        <section className="interview__code" aria-label="Your code">
          <div className="editor-toolbar">
            <span className="editor-toolbar__lang">Java</span>
            <span className="subtle">Your code is shared with the interviewer when you send a message.</span>
          </div>
          {problem.isError ? <ErrorState error={problem.error} onRetry={() => void problem.refetch()} />
            : problem.data ? <CodeEditor value={draft.code} onChange={draft.setCode} onSubmit={() => void onSend()} />
              : <LoadingState label="Loading editor…" />}
        </section>
      </div>
    </div>
  );
}

function InterviewResults({ iv }: { iv: Interview }) {
  const ev = iv.evaluation;
  const overall = ev ? OVERALL_LABELS[ev.overall] : null;
  const [showTranscript, setShowTranscript] = useState(false);
  const ending = { completed: "Completed", expired: "Time ran out", abandoned: "Ended early", in_progress: "" }[iv.status];
  return (
    <div className="page interview-results">
      <div className="page__header">
        <div>
          <h1 className="page__title">Interview feedback</h1>
          <p className="page__subtitle">{iv.problem.title} · {ending}</p>
        </div>
        <div className="row">
          <Link to="/interviews" className="btn btn--primary btn--md">Start another</Link>
          <Link to={`/problems/${iv.problem.slug}`} className="btn btn--secondary btn--md">Practice this problem</Link>
        </div>
      </div>

      {ev ? (
        <div className="interview-results__grid">
          <Card className="stack">
            <div className="row">
              <h2 className="section-title">Overall</h2>
              {overall && <Badge tone={overall.tone}>{overall.label}</Badge>}
              <span className="subtle">confidence: {ev.confidence}</span>
            </div>
            <p className="interview-results__summary">{ev.summary}</p>
            <RubricChart scores={ev.scores} />
          </Card>
          <div className="stack">
            <Card className="stack">
              <h2 className="section-title">What went well</h2>
              <ul className="strengths">{ev.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
            </Card>
            <Card className="stack">
              <h2 className="section-title">Focus next time</h2>
              <ul className="strengths">{ev.improvements.map((s) => <li key={s}>{s}</li>)}</ul>
            </Card>
            <p className="subtle">Feedback by: {iv.provider ?? "offline"}. It's a practice signal, not a hiring decision.</p>
          </div>
        </div>
      ) : (
        <p className="muted">No feedback was recorded for this interview.</p>
      )}

      <div className="stack interview-results__transcript">
        <Button variant="ghost" onClick={() => setShowTranscript((s) => !s)} aria-expanded={showTranscript}>
          {showTranscript ? "Hide transcript" : `Show transcript (${iv.turns.length} messages)`}
        </Button>
        {showTranscript && <Transcript turns={iv.turns} />}
        {showTranscript && iv.final_code && <pre className="final-code">{iv.final_code}</pre>}
      </div>
    </div>
  );
}
