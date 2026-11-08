import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { useInterviews, useProblems, useStartInterview } from "@/api/queries";
import type { InterviewSummary } from "@/api/types";
import { Badge, DifficultyBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";
import { timeAgo } from "@/lib/format";
import { Icon } from "@/components/Icon";

import { DIMENSION_LABELS, OVERALL_LABELS, PHASES } from "./phases";
import { ResumeCard } from "./ResumeCard";
import { conflictInterview } from "./resumeContext";
import { useActiveInterview } from "./useActiveInterview";

const DURATIONS = [15, 30, 45];

export function InterviewStartPage() {
  const navigate = useNavigate();
  const problems = useProblems({ page_size: 100 });
  const start = useStartInterview();
  const [slug, setSlug] = useState("");
  const [minutes, setMinutes] = useState(30);
  const running = useActiveInterview();
  // A Start refused because one is already live (another tab or device): that one, with context.
  const conflict = start.error instanceof ApiError && start.error.code === "interview_in_progress"
    ? conflictInterview(start.error.details)
    : null;
  const activeId = conflict?.id ?? running?.id ?? null;
  const activeSummary = conflict ? conflict.summary : running;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      const iv = await start.mutateAsync({ kind: "coding", purpose: "practice", problem_slug: slug || null, duration_minutes: minutes });
      navigate(`/interviews/${iv.id}`);
    } catch {
      /* rendered below */
    }
  }

  return (
    <div className="page interview-start">
      <div className="page__header">
        <div>
          <p className="eyebrow">THINK CLEARLY. EXPLAIN CONFIDENTLY.</p>
          <h1 className="page__title">Mock interview</h1>
          <p className="page__subtitle">A timed, realistic coding interview with an AI interviewer, then rubric feedback.</p>
          <p className="subtle">Or practise decisions in a <Link to="/scenarios">branching scenario</Link>.</p>
        </div>
      </div>
      <div className="interview-overview"><span><Icon name="clock" size={18} />15–45 minutes</span><span><Icon name="code" size={18} />Java workspace</span><span><Icon name="chart" size={18} />Feedback on {Object.keys(DIMENSION_LABELS).length} skills</span></div>

      <div className="interview-start__grid">
        <Card>
          <form className="stack" onSubmit={onSubmit} aria-labelledby="start-title">
            <h2 id="start-title" className="section-title"><Icon name="target" size={17} />Set up</h2>
            <p className="interview-start__lead">Make space to think.</p><p className="subtle">Choose your challenge and the time you want to spend on it.</p>
            <div className="field">
              <label className="field__label" htmlFor="iv-problem">Problem</label>
              <select id="iv-problem" className="select" value={slug} onChange={(e) => setSlug(e.target.value)}>
                <option value="">Pick one for me (recommended)</option>
                {problems.data?.items.map((p) => <option key={p.slug} value={p.slug}>{p.title} · {p.difficulty}</option>)}
              </select>
              {problems.isError && <InlineError error={problems.error} />}
            </div>
            <fieldset className="field">
              <legend className="field__label">Time limit</legend>
              <div className="segmented">
                {DURATIONS.map((d) => (
                  <label key={d} className={`segmented__option${minutes === d ? " segmented__option--active" : ""}`}>
                    <input type="radio" name="duration" value={d} checked={minutes === d} onChange={() => setMinutes(d)} />
                    {d} min
                  </label>
                ))}
              </div>
            </fieldset>
            {activeId ? <ResumeCard id={activeId} summary={activeSummary} alert={Boolean(conflict)} /> : <InlineError error={start.error} />}
            <Button type="submit" variant="primary" loading={start.isPending} disabled={Boolean(activeId)}>Start interview <Icon name="arrow" size={16} /></Button>
          </form>
        </Card>

        <Card className="stack">
          <h2 className="section-title">How it works</h2>
          <ol className="howto">
            {PHASES.map((p) => <li key={p.id}><strong>{p.label}.</strong> {HOWTO[p.id]}</li>)}
          </ol>
          <p className="subtle">The interviewer never writes code for you. Each reply uses one request from your daily AI budget;
            the final feedback is always free.</p>
        </Card>

        <Card className="stack">
          <h2 className="section-title"><Icon name="book" size={17} />Question round</h2>
          <p className="subtle">Practice the rest of the interview: five questions on why this job, what you know, a scenario,
            a time you did it, and leading others. Scored as you go.</p>
          <Link to="/interviews/questions" className="btn btn--secondary btn--md">Start a question round <Icon name="arrow" size={15} /></Link>
        </Card>
      </div>

      <PastInterviews />
    </div>
  );
}

const HOWTO: Record<string, string> = {
  clarify: "Restate the problem and ask about inputs and edge cases.",
  approach: "Explain your idea out loud before coding.",
  coding: "Write it in the editor and narrate your decisions.",
  complexity: "State time and space complexity and justify them.",
  wrap_up: "Walk through test cases, then finish for feedback.",
};

function PastInterviews() {
  const q = useInterviews({ page_size: 5 });
  return (
    <section className="stack interview-start__past" aria-label="Recent interviews">
      <h2 className="section-title">Recent interviews</h2>
      {q.isPending ? <LoadingState label="Loading interviews…" /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} />
        : q.data.total === 0 ? <EmptyState title="Your next interview starts with practice">Pick a problem and a time limit above. Your sessions and feedback will be saved here.</EmptyState>
          : <><ul className="interview-list">{q.data.items.map((iv) => <InterviewRow key={iv.id} iv={iv} />)}</ul>
            {q.data.total > 5 && <Link to="/history?type=interview">See all interviews</Link>}</>}
    </section>
  );
}

export function InterviewRow({ iv }: { iv: InterviewSummary }) {
  const overall = iv.overall ? OVERALL_LABELS[iv.overall] : null;
  return (
    <li>
      <Link to={`/interviews/${iv.id}`} className="interview-row">
        <span className="row">
          <strong>{iv.problem ? iv.problem.title : `${iv.career_title ?? "Career"} question round`}</strong>
          {iv.problem && <DifficultyBadge difficulty={iv.problem.difficulty} />}
        </span>
        <span className="row">
          {iv.status === "in_progress" ? <Badge tone="info">In progress</Badge> : overall ? <Badge tone={overall.tone}>{overall.label}</Badge>
            : iv.status === "completed" && <Badge>Completed</Badge>}
          {iv.average_score !== null && iv.average_score !== undefined && <span className="subtle">{iv.average_score.toFixed(1)}/4</span>}
          {iv.status === "expired" && <span className="subtle">time ran out</span>}
          {iv.status === "abandoned" && <span className="subtle">ended early</span>}
          <span className="subtle">{timeAgo(iv.started_at)}</span>
        </span>
      </Link>
    </li>
  );
}
