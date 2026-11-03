import { useEffect, useRef } from "react";

import { POLL_GIVE_UP_MS, useExplainFailure } from "@/api/queries";
import { useNow } from "@/hooks/useNow";
import type { Submission } from "@/api/types";
import { StatusBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Spinner } from "@/components/Spinner";
import { ErrorState, InlineError } from "@/components/States";
import { formatArgs, formatValue, timeAgo } from "@/lib/format";
import { Icon } from "@/components/Icon";

import { FailureExplanationView } from "./FailureExplanation";

const STATUS_COPY: Partial<Record<Submission["status"], string>> = {
  PASSED: "All tests passed. Nice work.",
  FAILED: "Some tests failed. Check the cases below.",
  COMPILE_ERROR: "Your code didn't compile.",
  RUNTIME_ERROR: "Your program crashed or exited before finishing all the tests.",
  TIME_LIMIT: "Your code ran too long. Look for an infinite loop or a slower-than-needed approach.",
  MEMORY_LIMIT: "Your code used too much memory.",
  INTERNAL_ERROR: "The judge had a problem. This wasn't your fault; try again.",
};

const isRunMode = (s: Submission) => s.mode === "run";

/** Verdicts caused by the learner's code, which the coach can explain. */
const EXPLAINABLE: ReadonlySet<Submission["status"]> = new Set([
  "FAILED", "COMPILE_ERROR", "RUNTIME_ERROR", "TIME_LIMIT", "MEMORY_LIMIT",
]);

interface SubmissionPanelProps {
  submission: Submission | undefined;
  error: unknown;
  onHighlightLine?(line: number | null): void;
}

export function SubmissionPanel({ submission, error, onHighlightLine }: SubmissionPanelProps) {
  const now = useNow();
  if (error) return <ErrorState error={error} />;
  if (!submission) {
    return (
      <div className="results results--empty">
        <Icon name="terminal" size={24} />
        <strong>Your next result starts with an attempt.</strong>
        <p className="muted">Submit your solution to save an attempt. <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd></p>
      </div>
    );
  }
  const running = !submission.is_terminal && submission.execution_enabled;
  const statusText = running
    ? submission.status === "RUNNING"
      ? isRunMode(submission) ? "Running your code against the public tests…" : "Running your code against the tests…"
      : submission.status_detail
    : null;
  const result = submission.result;
  const isRun = submission.mode === "run";
  return (
    <div className="results" aria-live="polite">
      <h2 className="section-title results__label"><Icon name="terminal" size={15} />Execution results</h2>
      <div className="results__header">
        <StatusBadge status={submission.status} />
        {running && <Spinner size="sm" label="Judging" />}
        {isRun && <span className="badge badge--info">Run · public tests only</span>}
        <span className="subtle">{isRun ? "Ran" : "Submitted"} {timeAgo(submission.created_at)}</span>
      </div>
      {statusText && <p className="subtle" role="status">{statusText}</p>}
      {running && now - new Date(submission.created_at).getTime() > POLL_GIVE_UP_MS && (
        <p className="banner banner--warning" role="status">
          Still waiting after 15 minutes, so this page stopped checking. It will be judged when the judge catches up; reload the page to check again.
        </p>
      )}

      {!submission.execution_enabled && (
        <div className="banner" role="status">
          <strong>Saved, but not run yet.</strong> {submission.status_detail}
          <div className="subtle">Meanwhile, ask the AI coach for a review of this code.</div>
        </div>
      )}

      {submission.is_terminal && STATUS_COPY[submission.status] && (
        <p className={submission.status === "PASSED" ? "results__verdict results__verdict--pass" : "results__verdict"}>
          {isRun && submission.status === "PASSED"
            ? "All public tests passed. Submit to check the hidden tests and record the attempt."
            : STATUS_COPY[submission.status]}
        </p>
      )}

      {submission.is_terminal && EXPLAINABLE.has(submission.status) && (
        <ExplainFailure key={submission.id} submissionId={submission.id} onHighlightLine={onHighlightLine} />
      )}

      {result && (
        <>
          <div className="results__stats">
            <span><strong>{result.passed_count}</strong>/{result.total_count} tests passed</span>
            {result.hidden_total > 0 && (
              <span className="subtle">hidden: {result.hidden_passed}/{result.hidden_total}</span>
            )}
            {result.runtime_ms !== null && result.runtime_ms !== undefined && (
              <span className="subtle" title="Time spent inside your method across all tests">{result.runtime_ms} ms</span>
            )}
            {result.memory_kb !== null && result.memory_kb !== undefined && (
              <span className="subtle">{Math.round(result.memory_kb / 1024)} MB</span>
            )}
          </div>
          {submission.status === "COMPILE_ERROR" && result.stderr_excerpt && (
            <div className="stack">
              <span className="section-title">Compiler output</span>
              <pre className="stderr">{result.stderr_excerpt}</pre>
            </div>
          )}
          <ul className="case-list">
            {result.public_results.map((r) => (
              <li key={r.index} className={`case case--${r.passed ? "pass" : "fail"}`}>
                <span className="case__icon" aria-label={r.passed ? "passed" : "failed"}>{r.passed ? "✓" : "✗"}</span>
                <span>
                  {r.input && <code>{formatArgs(r.input)}</code>}
                  {!r.passed && (
                    <span className="case__detail">
                      expected <code>{formatValue(r.expected_output)}</code>
                      {r.missing ? (
                        <>, but this test never ran (the program stopped first)</>
                      ) : r.exception ? (
                        <>
                          , but it threw <code>{r.exception}</code>{r.exception_message ? <>: {r.exception_message}</> : null}
                          {r.line && (onHighlightLine ? (
                            <> at <button type="button" className="link-button" onClick={() => onHighlightLine(r.line ?? null)}>line {r.line}</button></>
                          ) : <> at line {r.line}</>)}
                        </>
                      ) : (
                        <>, got <code>{formatValue(r.actual_output)}</code></>
                      )}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function ExplainFailure({ submissionId, onHighlightLine }: { submissionId: string; onHighlightLine?(line: number | null): void }) {
  const explain = useExplainFailure();
  const cardRef = useRef<HTMLElement>(null);
  // The results panel scrolls independently, so bring the new explanation into view (and keep
  // keyboard users on it). Smooth scrolling is skipped when the user prefers reduced motion.
  useEffect(() => {
    const card = cardRef.current;
    if (!explain.data || !card) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    card.scrollIntoView?.({ block: "start", behavior: reduce ? "auto" : "smooth" });
    card.focus({ preventScroll: true });
  }, [explain.data]);
  if (explain.data) {
    return (
      <section ref={cardRef} tabIndex={-1} className="explain card" aria-label="Why it failed">
        <h3 className="section-title">Why it failed</h3>
        <FailureExplanationView data={explain.data} onHighlightLine={onHighlightLine} />
      </section>
    );
  }
  return (
    <div className="explain-cta">
      <Button size="sm" variant="secondary" loading={explain.isPending} onClick={() => explain.mutate(submissionId)}>
        Explain this failure
      </Button>
      <span className="subtle">Uses the public tests and compiler output only.</span>
      <InlineError error={explain.error} />
    </div>
  );
}
