import { useId, useState, type FormEvent } from "react";

import type { CheckResult, LearnUnit } from "@/api/types";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";
import { useStoredDraft } from "@/hooks/useStoredDraft";

/** A scrollable, keyboard-reachable code block with a name for screen readers. */
export function CodeBlock({ code, language, label }: { code: string; language: string | null; label: string }) {
  return (
    <pre className="code-block" tabIndex={0} role="region" aria-label={`${language ? `${language[0]!.toUpperCase()}${language.slice(1)} code` : "Code"}: ${label}`}>
      <code>{code}</code>
    </pre>
  );
}

const STEP_NAMES = ["A question to think about", "The key concept", "An example", "The fuller explanation"];

/**
 * The exercise: a draft box that is never overwritten, guided help revealed one step at a time,
 * or (independent mode) a solution kept hidden until the learner confirms they want to see it.
 */
export function ExerciseSection({ unit, draftKey }: { unit: LearnUnit; draftKey: string }) {
  const e = unit.exercise;
  const [draft, setDraft] = useStoredDraft(draftKey);
  const [mode, setMode] = useState<"guided" | "independent">("guided");
  const [steps, setSteps] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const [solution, setSolution] = useState(false);
  const id = useId();

  return (
    <section className="learn-section stack" id="exercise" aria-labelledby={`${id}-title`}>
      <h2 className="section-title" id={`${id}-title`}>Try it</h2>
      <p>{e.prompt}</p>
      <fieldset className="learn-mode">
        <legend>How much help do you want?</legend>
        <label><input type="radio" name={`${id}-mode`} checked={mode === "guided"} onChange={() => setMode("guided")} /> Guided: hints one step at a time</label>
        <label><input type="radio" name={`${id}-mode`} checked={mode === "independent"} onChange={() => setMode("independent")} /> On my own: solution only if I ask</label>
      </fieldset>
      <label className="field">
        <span className="field__label">{e.draft_label}</span>
        <textarea className={`input learn-draft${e.solution_language ? " learn-draft--code" : ""}`} rows={8} value={draft}
          spellCheck={!e.solution_language} onChange={(ev) => setDraft(ev.target.value)}
          aria-describedby={`${id}-draft-note`} />
      </label>
      <p className="subtle" id={`${id}-draft-note`}>Your draft is saved in this browser. Revealing help or the solution never changes it.</p>

      {mode === "guided" ? (
        <div className="stack-sm">
          <ol className="learn-steps" aria-live="polite">
            {e.guided_steps.slice(0, steps).map((text, i) => (
              <li key={i}><strong>{STEP_NAMES[i]}:</strong> {text}</li>
            ))}
          </ol>
          {steps < e.guided_steps.length ? (
            <Button size="sm" onClick={() => setSteps(steps + 1)}>
              Show step {steps + 1} of {e.guided_steps.length}: {STEP_NAMES[steps]?.toLowerCase()}
            </Button>
          ) : <p className="subtle">That's all the guided help. Compare it with your draft, then take the check.</p>}
        </div>
      ) : solution ? (
        <div className="stack-sm learn-solution">
          <h3 className="learn-subtitle">Solution</h3>
          {e.solution_language
            ? <CodeBlock code={e.solution} language={e.solution_language} label="solution" />
            : <p>{e.solution}</p>}
          <Button size="sm" variant="ghost" onClick={() => setSolution(false)}>Hide the solution</Button>
        </div>
      ) : confirming ? (
        <div className="banner banner--warning stack-sm" role="alertdialog" aria-labelledby={`${id}-spoiler`}>
          <strong id={`${id}-spoiler`}>Spoiler: this shows a complete solution.</strong>
          <p>Try it yourself first if you can. Your draft stays exactly as it is.</p>
          <span className="row">
            <Button size="sm" variant="primary" autoFocus onClick={() => { setSolution(true); setConfirming(false); }}>Show the solution</Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>Not yet</Button>
          </span>
        </div>
      ) : (
        <Button size="sm" onClick={() => setConfirming(true)}>Show solution…</Button>
      )}
    </section>
  );
}

/** The comprehension check: graded on the server; shows each answer's explanation afterwards. */
export function CheckSection({ unit, signedIn, onSubmit, pending, error, result, offline = false }: {
  unit: LearnUnit;
  signedIn: boolean;
  /** Grading happens on the server: offline, the check can be answered but not submitted. */
  offline?: boolean;
  onSubmit(answers: Record<string, number>): void;
  pending: boolean;
  error: unknown;
  result: CheckResult | null;
}) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const id = useId();
  const byId = new Map(result?.results.map((r) => [r.id, r]));

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit(answers);
  }

  return (
    <section className="learn-section stack" id="check" aria-labelledby={`${id}-title`}>
      <h2 className="section-title" id={`${id}-title`}>Check yourself</h2>
      <p className="subtle">{unit.check.length} questions. Passing means: {unit.pass_rule.toLowerCase()} Reading the unit alone doesn't count as passing.</p>
      <form className="stack" onSubmit={submit}>
        {unit.check.map((q, n) => {
          const r = byId.get(q.id);
          return (
            <fieldset key={q.id} className={`learn-question${r ? (r.correct ? " learn-question--right" : " learn-question--wrong") : ""}`}>
              <legend>{n + 1}. {q.prompt}</legend>
              {q.options.map((opt, i) => (
                <label key={i} className="learn-option">
                  <input type="radio" name={`${id}-${q.id}`} checked={answers[q.id] === i}
                    onChange={() => setAnswers({ ...answers, [q.id]: i })} />
                  {opt}
                </label>
              ))}
              {r && (
                <p className="learn-feedback">
                  <strong>{r.correct ? "Right." : r.chosen === null || r.chosen === undefined ? "Not answered." : "Not quite."}</strong>{" "}
                  {!r.correct && <>The answer is “{q.options[r.answer]}”. </>}{r.explanation}
                </p>
              )}
            </fieldset>
          );
        })}
        {signedIn && offline ? (
          <p className="subtle">You're offline. Checking your answers needs a connection; your choices stay on this page.</p>
        ) : signedIn ? (
          <Button type="submit" variant="primary" loading={pending}>{result ? "Check again" : "Check my answers"}</Button>
        ) : (
          <p className="subtle">Sign in or start a guest session to have your answers checked and saved.</p>
        )}
        <InlineError error={error} />
        {result && (
          <p className={`banner ${result.passed ? "banner--success" : "banner--warning"}`} role="status">
            {result.passed
              ? `Passed: ${result.correct} of ${result.total} right. This is recorded for version ${unit.version}; it doesn't mark any problem solved.`
              : `${result.correct} of ${result.total} right. Read the explanations and try again; every attempt is kept.`}
          </p>
        )}
      </form>
    </section>
  );
}
