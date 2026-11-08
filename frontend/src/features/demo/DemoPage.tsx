import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useCapabilities, useDemo } from "@/api/queries";
import type { DemoPersona } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";
import { canSpeak, recognitionCtor } from "@/features/voice/capabilities";

const BACK = { from: "/demo", fromLabel: "Back to the demo" };

/**
 * The portfolio demo's entry (Volume 7, prompt 10; docs/DEMO.md): who the fictional sample learners
 * are, what this server can actually do right now, and a few things to try, each a direct link
 * that comes back here. Starting gives the visitor their own guest session. No tour.
 */
export function DemoPage() {
  const capabilities = useCapabilities();
  const demoMode = capabilities.data?.demo_mode === true;
  const demo = useDemo(demoMode);
  const { user, isAuthenticated, continueAsGuest } = useAuth();
  const navigate = useNavigate();
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  if (capabilities.isPending) return <div className="page"><LoadingState /></div>;
  if (!demoMode) {
    return (
      <div className="page">
        <EmptyState pageTitle title="This server isn't running the demo"
          action={<Link className="btn btn--primary btn--md" to="/">Go to the start page</Link>}>
          The guided demo runs on a demo server with fictional data (see docs/DEMO.md). Here you can still try CodeCoach as a guest.
        </EmptyState>
      </div>
    );
  }

  async function start(persona: DemoPersona) {
    setStarting(persona.key);
    setError(null);
    try {
      await continueAsGuest("Demo visitor", persona.career_track);
      navigate(`/careers/${persona.career_track}/questions/${persona.start_question_id}`, { state: BACK });
    } catch (e) {
      setError(e);
    } finally {
      setStarting(null);
    }
  }

  const caps = capabilities.data!;
  const personas = demo.data?.personas ?? [];
  const mine = personas.find((p) => p.career_track === user?.career_track) ?? null;
  return (
    <div className="page demo-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">DEMO · FICTIONAL DATA</p>
          <h1 className="page__title">Try CodeCoach with a sample learner</h1>
          <p className="page__subtitle">
            Pick a career below and you get your own demo session: only you can see what you write in it. The learners
            and their answers are made up.
          </p>
        </div>
      </div>

      <section className="card stack-sm demo-page__server" aria-labelledby="demo-server">
        <h2 className="section-title" id="demo-server">What this demo server can do right now</h2>
        <dl className="demo-page__caps">
          <div><dt>Code judge</dt><dd>{caps.execution.state === "ready" ? "Runs and judges your code in an isolated sandbox." : caps.execution.message}</dd></div>
          <div><dt>AI coach</dt><dd>{caps.ai_provider === "anthropic"
            ? "A live AI provider answers hints and reviews, with a daily limit per visitor."
            : "The built-in coach: curated hints and checks written for each problem. No AI service is called."}</dd></div>
          <div><dt>Email</dt><dd>None is sent. Accounts can't be created here; your demo session doesn't need one.</dd></div>
          <div><dt>Voice (this browser)</dt><dd>{voiceText()}</dd></div>
        </dl>
      </section>

      {isAuthenticated && user?.is_guest && (
        <Card className="stack-sm demo-page__steps">
          <h2 className="section-title">Things to try (about ten minutes)</h2>
          <Steps persona={mine} />
        </Card>
      )}

      {demo.isPending ? <LoadingState label="Loading the sample learners…" />
        : demo.isError ? <ErrorState error={demo.error} onRetry={() => void demo.refetch()} action="Loading the demo" />
          : (
            <div className="demo-page__personas">
              {personas.map((p) => (
                <section key={p.key} className="card stack-sm demo-persona" aria-labelledby={`persona-${p.key}`}>
                  <h2 className="section-title" id={`persona-${p.key}`}>{p.name} <span className="subtle">(fictional) · {p.career_title}</span></h2>
                  <p>{p.summary}</p>
                  {!isAuthenticated && (
                    <span>
                      <Button variant="primary" loading={starting === p.key} disabled={starting !== null} onClick={() => void start(p)}>
                        Start a demo session as a {p.career_title.toLowerCase()}
                      </Button>
                    </span>
                  )}
                  <details className="demo-persona__examples">
                    <summary>{p.name}'s example answers ({p.examples.length})</summary>
                    {p.examples.map((e) => (
                      <article key={e.question_id} className="demo-example stack-sm" aria-label={`Example: ${e.question_title}`}>
                        <h3 className="demo-example__title">{e.question_title}</h3>
                        <p className="demo-example__label"><strong>Example.</strong> {e.label}</p>
                        <p className="demo-example__score">Score {e.score}/100 · {e.rating}</p>
                        <p>{e.summary}</p>
                        <blockquote className="demo-example__answer">{e.answer}</blockquote>
                      </article>
                    ))}
                  </details>
                </section>
              ))}
            </div>
          )}
      <InlineError error={error} action="Starting the demo session" />
      <ul className="subtle demo-page__notes">{demo.data?.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </div>
  );
}

function Steps({ persona }: { persona: DemoPersona | null }) {
  if (!persona) {
    return <p>Your demo session is for a career the sample learners don't cover. <Link to="/dashboard">Open your dashboard</Link>.</p>;
  }
  const question = `/careers/${persona.career_track}/questions/${persona.start_question_id}`;
  return (
    <ol className="demo-steps">
      <li>
        <Link to={question} state={BACK}>Answer “{persona.start_question_title}”</Link>: written feedback from the
        built-in grader, with what your answer covered and what it missed.
      </li>
      {persona.problem_slug && (
        <li>
          <Link to={`/problems/${persona.problem_slug}`} state={BACK}>Open a coding problem</Link> and ask the coach for a hint.
          Without a code judge on the server, Submit saves your attempt and says it wasn't run: it never shows a result it didn't get.
        </li>
      )}
      <li><Link to="/interviews" state={BACK}>Run a short mock interview</Link>, typed or spoken.</li>
      <li>
        <strong>Leave and come back:</strong> start the interview, answer one question, then reload the page or open it in
        another tab. It carries on where you were, and the draft you were typing is still there.
      </li>
      <li><Link to="/dashboard" state={BACK}>See your progress</Link>, built from what you just did.</li>
    </ol>
  );
}

function voiceText(): string {
  const listen = !!recognitionCtor();
  const speak = canSpeak();
  if (listen && speak) return "Speaking answers and the interviewer's voice both work here (typing always does).";
  if (speak) return "The interviewer's voice works here; speaking answers needs Chrome, Edge or Safari. Typing always works.";
  if (listen) return "Speaking answers works here; this browser has no interviewer voice. Typing always works.";
  return "This browser has no speech features; everything works by typing.";
}
