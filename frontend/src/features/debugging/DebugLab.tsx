import { useId, useState } from "react";

import { useLabExplanation } from "@/api/queries";
import type { ProblemDetail, Submission } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { ErrorState } from "@/components/States";
import { formatArgs, formatValue } from "@/lib/format";

import { changedHunks, lineDiff } from "./lineDiff";
import { debugNotesKey } from "./notesKey";

/**
 * The debugging lab on the coding workspace (Volume 10, prompt 2; docs/DEBUGGING_LAB.md). The
 * starter is the faulty code. The brief says what the code should do and which public cases show
 * the defect; optional investigation notes stay on this device; the defect's explanation and one
 * repair appear only when the learner asks (or once the fix passes). The verdict is always the
 * judge's: any repair that passes every test is accepted, whatever it looks like.
 */
export function DebugBrief({ problem }: { problem: ProblemDetail }) {
  const lab = problem.lab;
  const [asking, setAsking] = useState(false);
  const [shown, setShown] = useState(false);
  const titleId = useId();
  if (!lab) return null;
  const failing = problem.public_tests.filter((t) => lab.reproduction_test_ids.includes(t.id));
  return (
    <section className="debug-brief card stack-sm" aria-labelledby={titleId}>
      <p className="eyebrow">DEBUGGING EXERCISE</p>
      <h2 className="section-title" id={titleId}>Fix the bug</h2>
      <p><strong>What it should do:</strong> {lab.intended_behavior}</p>
      <div className="stack-sm">
        <h3 className="debug-brief__subtitle">Reproduce it</h3>
        <p>With the code as given, {failing.length === 1 ? "this public case fails" : "these public cases fail"}. Run the code to see what it returns instead.</p>
        <ul className="debug-brief__cases">
          {failing.map((t) => (
            <li key={t.id}><code>{formatArgs(t.input)}</code> should give <code>{formatValue(t.expected_output)}</code></li>
          ))}
        </ul>
      </div>
      <InvestigationNotes slug={problem.slug} />
      {shown ? (
        <ExplanationView slug={problem.slug} heading="What the defect is" />
      ) : asking ? (
        <div className="banner banner--info stack-sm" role="group" aria-label="Show the explanation?">
          <p>This shows what the defect is, why a simple case misses it, and one correct repair. You can still write your own fix afterwards: any fix that passes is accepted.</p>
          <span className="row">
            <Button size="sm" variant="primary" onClick={() => setShown(true)}>Show the explanation</Button>
            <Button size="sm" variant="ghost" onClick={() => setAsking(false)}>Not yet</Button>
          </span>
        </div>
      ) : (
        <p><Button size="sm" variant="secondary" onClick={() => setAsking(true)}>Stuck? Show the explanation</Button></p>
      )}
      <p className="subtle debug-brief__meta">Exercise version {lab.version}. {lab.review_status}</p>
    </section>
  );
}

const NOTE_FIELDS = [
  { key: "observed", label: "What you observed" },
  { key: "hypothesis", label: "Your hypothesis" },
  { key: "next_case", label: "Next case to try" },
] as const;
type Notes = Partial<Record<(typeof NOTE_FIELDS)[number]["key"], string>>;

function readNotes(key: string | null): Notes {
  if (!key) return {};
  try {
    const raw = JSON.parse(window.localStorage.getItem(key) ?? "{}") as unknown;
    return raw && typeof raw === "object" ? (raw as Notes) : {};
  } catch {
    return {};
  }
}

/** Optional: nothing here is needed for a result, and nothing is sent. Signed in, the notes are kept
 * in this browser for this account (removed at sign-out); signed out, they last as long as the page. */
function InvestigationNotes({ slug }: { slug: string }) {
  const { user, isAuthenticated } = useAuth();
  const key = isAuthenticated && user ? debugNotesKey(user.id, slug) : null;
  const [notes, setNotes] = useState<Notes>(() => readNotes(key));
  const ids = useId();
  const update = (field: keyof Notes, value: string) => {
    const next = { ...notes, [field]: value };
    setNotes(next);
    if (!key) return;
    try {
      if (Object.values(next).some((v) => v?.trim())) window.localStorage.setItem(key, JSON.stringify(next));
      else window.localStorage.removeItem(key);
    } catch { /* storage blocked: they last as long as the page */ }
  };
  return (
    <details className="debug-notes">
      <summary>Your investigation (optional)</summary>
      <p className="subtle">Notes for yourself: not needed for a result and not sent anywhere. {key ? "Kept in this browser for your account until you sign out." : "Sign in to keep them in this browser."}</p>
      {NOTE_FIELDS.map((f) => (
        <label key={f.key} className="field" htmlFor={`${ids}-${f.key}`}>
          <span className="field__label">{f.label}</span>
          <textarea id={`${ids}-${f.key}`} className="input" rows={2} maxLength={2000} value={notes[f.key] ?? ""}
            onChange={(e) => update(f.key, e.target.value)} />
        </label>
      ))}
    </details>
  );
}

function ExplanationView({ slug, heading }: { slug: string; heading: string }) {
  const explanation = useLabExplanation(slug, true);
  if (explanation.isPending) return <p className="subtle" role="status">Loading the explanation…</p>;
  if (explanation.isError) return <ErrorState error={explanation.error} onRetry={() => void explanation.refetch()} />;
  const e = explanation.data;
  return (
    <div className="debug-explanation stack-sm">
      <h3 className="debug-brief__subtitle">{heading}</h3>
      <p><strong>{e.defect_summary}</strong></p>
      <p>{e.explanation}</p>
      <h4 className="debug-brief__minor">Why a simple case missed it</h4>
      <p>{e.why_missed}</p>
      <h4 className="debug-brief__minor">One correct repair</h4>
      <p className="subtle">Yours doesn't have to look like this: the tests decide.</p>
      <pre className="code-block"><code>{e.reference_repair}</code></pre>
      <h4 className="debug-brief__minor">Next time</h4>
      <p>{e.follow_up}</p>
    </div>
  );
}

/**
 * After an attempt: the judge's verdict in the lab's terms, which of the reproduction cases now
 * pass, and what was changed from the code the attempt started from. The verdict comes only from
 * the tests that ran; a saved, unjudged attempt says it couldn't be checked.
 */
export function DebugDebrief({ problem, submission }: { problem: ProblemDetail; submission: Submission | undefined }) {
  const lab = problem.lab;
  if (!lab || !submission || submission.mode !== "submit" || !submission.starting_code) return null;
  if (!submission.is_terminal && submission.execution_enabled) return null; // still judging: the panel says so
  const result = submission.result;
  const repro = problem.public_tests.filter((t) => lab.reproduction_test_ids.includes(t.id));
  const outcomeFor = (input: Record<string, unknown>) =>
    result?.public_results.find((r) => JSON.stringify(r.input) === JSON.stringify(input));
  const diff = lineDiff(submission.starting_code, submission.source_code);
  const changes = diff ? changedHunks(diff) : null;
  const passed = submission.status === "PASSED";
  return (
    <section className="debug-debrief card stack-sm" aria-label="Debugging debrief">
      <h3 className="debug-brief__subtitle">
        {!submission.execution_enabled ? "Saved, not checked"
          : passed ? "Fixed: every test passes"
            : result ? `Not fixed yet: ${result.passed_count} of ${result.total_count} tests pass` : "Not fixed yet"}
      </h3>
      {!submission.execution_enabled && <p>Code can't run on this server, so whether this fixes the defect can't be checked. Your attempt is saved.</p>}
      {submission.lab_version != null && submission.lab_version !== lab.version && (
        <p className="subtle">This attempt was made on version {submission.lab_version} of the exercise; it's version {lab.version} now.</p>
      )}
      {result && repro.length > 0 && (
        <ul className="debug-brief__cases" aria-label="The cases that showed the defect">
          {repro.map((t) => {
            const r = outcomeFor(t.input);
            return (
              <li key={t.id}>
                <code>{formatArgs(t.input)}</code>:{" "}
                {r ? (r.passed ? "now passes" : `still fails (got ${r.exception ? r.exception : formatValue(r.actual_output)}, expected ${formatValue(t.expected_output)})`) : "not run"}
              </li>
            );
          })}
        </ul>
      )}
      {changes && (
        <details className="debug-diff" open={changes.some((c) => c !== "gap" && c.kind !== "same")}>
          <summary>What you changed from the starting code</summary>
          {changes.some((c) => c !== "gap" && c.kind !== "same") ? (
            <pre className="code-block debug-diff__lines">{changes.map((c, k) => (
              c === "gap" ? <span key={k} className="debug-diff__gap">…{"\n"}</span>
                : <span key={k} className={`debug-diff__${c.kind}`}>{c.kind === "added" ? "+ " : c.kind === "removed" ? "- " : "  "}{c.text}{"\n"}</span>
            ))}</pre>
          ) : <p>Nothing: this is the starting code as given.</p>}
        </details>
      )}
      {passed && <ExplanationView slug={problem.slug} heading="Why it happened" />}
    </section>
  );
}
