import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";
import { BrandMark } from "@/components/BrandMark";
import { ProductPreview } from "./ProductPreview";

const STEPS = [
  { title: "Pick a problem", body: "Curated Java interview problems with clear contracts, examples and edge cases." },
  { title: "Write real code", body: "A full code editor with Java syntax, autosaved drafts and keyboard shortcuts." },
  { title: "Get coached, not spoiled", body: "Hints unlock one level at a time: a nudge, then the concept, then pseudocode." },
  { title: "Trust the verdict", body: "Pass or fail comes from hidden test cases. The AI reviews your code but never grades it." },
];

export function LandingPage() {
  const { isAuthenticated, continueAsGuest } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function tryDemo() {
    setBusy(true);
    setError(null);
    try {
      if (isAuthenticated) {
        navigate("/problems/two-sum");
      } else {
        // A deliberate demo: a guest session, then the optional welcome to choose how to start.
        await continueAsGuest();
        navigate("/welcome");
      }
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="landing">
      <section className="landing__hero">
        <p className="landing__eyebrow"><span />YOUR NEXT CHAPTER STARTS WITH PRACTICE</p>
        <h1 className="landing__title">Practice like it's{" "}<br />the <span>real interview.</span></h1>
        <p className="landing__lead">
          Think it through. Write real Java. Get coaching that helps you move forward.
          Build the skills to walk into your next interview with confidence.
        </p>
        <div className="row landing__cta">
          <Button variant="primary" onClick={tryDemo} loading={busy}>
            {isAuthenticated ? "Open a problem" : "Try it now, no sign-up"}
          </Button>
          <Link to="/problems" className="btn btn--secondary btn--md">Browse problems</Link>
        </div>
        <InlineError error={error} />
        <div className="landing__assurances"><span>Java-first workspace</span><span>Progressive coaching</span><span>Your progress, saved</span></div>
      </section>

      <ProductPreview />

      <section className="landing__steps" aria-label="How it works">
        <div className="landing__section-heading"><p className="eyebrow">THE PRACTICE LOOP</p><h2>Go beyond getting the answer.</h2><p className="muted">Build a repeatable way to solve the next problem, too.</p></div>
        {STEPS.map((step, i) => (
          <div className="landing__step" key={step.title}>
            <span className="landing__step-num">0{i + 1}</span>
            <h2>{step.title}</h2>
            <p className="muted">{step.body}</p>
          </div>
        ))}
      </section>
      <section className="landing__interview">
        <div><p className="eyebrow">PUT IT ALL TOGETHER</p><h2>A little pressure.<br />A lot to learn.</h2><p className="muted">Practice explaining your approach in a timed mock interview. Get follow-up questions and feedback on five skills, with your transcript saved for later.</p></div>
        <div className="landing__interview-action"><span className="badge badge--info">15 / 30 / 45 minutes</span><Link className="btn btn--secondary btn--md" to={isAuthenticated ? "/interviews" : "/login"} state={{ from: "/interviews" }}>Explore mock interviews <span aria-hidden="true">→</span></Link><p className="subtle">Available with an account or guest session.</p></div>
      </section>
      <footer className="landing__footer"><Link className="brand" to="/" aria-label="CodeCoach AI home"><BrandMark />CodeCoach AI</Link><p>Practice with purpose. Build with confidence.</p><nav aria-label="Footer"><Link to="/problems">Practice</Link><Link to="/register">Create account</Link><a href="https://github.com/Barkyx16/CodeCoach-AI" target="_blank" rel="noopener noreferrer">GitHub <span className="visually-hidden">(opens in a new tab)</span></a></nav></footer>
    </div>
  );
}
