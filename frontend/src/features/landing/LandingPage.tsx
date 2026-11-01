import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";

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
      if (!isAuthenticated) await continueAsGuest();
      navigate("/problems/two-sum");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="landing">
      <section className="landing__hero">
        <p className="landing__eyebrow">Java interview practice · AI coach · real test judge</p>
        <h1 className="landing__title">Practice like it's the real interview.<br />Get coached like you have a mentor.</h1>
        <p className="landing__lead">
          CodeCoach AI gives you progressive hints and structured code reviews without handing you the answer.
          Correctness always comes from test cases, never from the AI.
        </p>
        <div className="row landing__cta">
          <Button variant="primary" onClick={tryDemo} loading={busy}>
            {isAuthenticated ? "Open a problem" : "Try it now, no sign-up"}
          </Button>
          <Link to="/problems" className="btn btn--secondary btn--md">Browse problems</Link>
        </div>
        <InlineError error={error} />
      </section>

      <section className="landing__preview" aria-label="Workspace preview">
        <div className="preview">
          <div className="preview__panel">
            <span className="preview__label">Problem</span>
            <strong>Two Sum</strong>
            <span className="badge badge--difficulty-easy">Easy</span>
            <p className="subtle">Return the indices of two numbers that add up to the target.</p>
          </div>
          <pre className="preview__code">{`class Solution {
  public int[] twoSum(int[] nums, int target) {
    Map<Integer, Integer> seen = new HashMap<>();
    // ...
  }
}`}</pre>
          <div className="preview__panel">
            <span className="preview__label">AI coach</span>
            <p className="subtle">“For each number, you already know which value you'd need. How could you check whether you've seen it?”</p>
            <span className="badge badge--info">Hint 1 of 4 · nudge</span>
          </div>
        </div>
      </section>

      <section className="landing__steps" aria-label="How it works">
        {STEPS.map((step, i) => (
          <div className="landing__step" key={step.title}>
            <span className="landing__step-num">{i + 1}</span>
            <h2>{step.title}</h2>
            <p className="muted">{step.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
