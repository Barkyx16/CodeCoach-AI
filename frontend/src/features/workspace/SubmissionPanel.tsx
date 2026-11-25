import { useEffect, useRef, useState } from "react";

import { POLL_GIVE_UP_MS, useExplainFailure } from "@/api/queries";
import { useNow } from "@/hooks/useNow";
import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import type { CoachPreview, Submission } from "@/api/types";
import { ActionError } from "@/components/ActionError";
import { CoachContext, REFUSED, type ChoiceKey } from "@/features/workspace/CoachContext";
import { StatusBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Spinner } from "@/components/Spinner";
import { ErrorState, InlineError } from "@/components/States";
import { formatArgs, formatValue, timeAgo } from "@/lib/format";
import { Icon } from "@/components/Icon";

import { FailureExplanationView } from "./FailureExplanation";
import { FollowsUpNote } from "./ProblemFollowUps";
import { SubmissionCompared } from "./SubmissionCompared";
import { FeedbackKind } from "@/components/FeedbackKind";

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
  /** The editor's code now: when it differs, the result says it's for the code that was sent. */
  editorCode?: string;
  /** One more status read, after the page stopped checking by itself. */
  onCheckAgain?(): void;
  checking?: boolean;
}

export function SubmissionPanel({ submission, error, onHighlightLine, editorCode, onCheckAgain, checking = false }: SubmissionPanelProps) {
  const now = useNow();
  // Nothing to show yet: the error is all there is. With a result on screen, a failed refresh
  // doesn't take it away (below).
  if (error && !submission) return <ErrorState error={error} />;
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
      <FeedbackKind kind="results" />
      <div className="results__header">
        <StatusBadge status={submission.status} />
        {running && <Spinner size="sm" label="Judging" />}
        {isRun && <span className="badge badge--info">Run · public tests only</span>}
        <span className="subtle">{isRun ? "Ran" : "Submitted"} {timeAgo(submission.created_at)}</span>
      </div>
      {editorCode !== undefined && submission.source_code !== undefined && submission.source_code !== editorCode && (
        <p className="subtle" data-testid="result-source">
          {running ? "This is judging" : "This result is for"} the code as {isRun ? "run" : "submitted"} {timeAgo(submission.created_at)}.
          The editor has changed since; {isRun ? "run" : "submit"} again to check the current code.
        </p>
      )}
      {submission.follows_up && <FollowsUpNote of={submission.follows_up} />}
      {statusText && <p className="subtle" role="status">{statusText}</p>}
      {error != null && (
        <p className="subtle" role="status">
          We couldn't check for an update just now. This is the latest result we have; it updates when the connection is back.
        </p>
      )}
      {running && now - new Date(submission.created_at).getTime() > POLL_GIVE_UP_MS && (
        <div className="banner banner--warning" role="status">
          Still waiting after 15 minutes, so this page stopped checking by itself. It stays in the queue and will be
          judged when the judge catches up. Leaving this page doesn't stop it.
          {onCheckAgain && <div><Button size="sm" variant="secondary" loading={checking} onClick={onCheckAgain}>Check again</Button></div>}
        </div>
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
          {submission.is_terminal && submission.compared && <SubmissionCompared current={submission} compared={submission.compared} />}
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
        <FeedbackKind kind="explanation" />
        <FailureExplanationView data={explain.data} onHighlightLine={onHighlightLine} />
      </section>
    );
  }
  return <ExplainCheck submissionId={submissionId} explain={explain} />;
}

/** Check, then send (docs/COACH_CONTEXT.md): what the explanation would read, for this submission. */
function ExplainCheck({ submissionId, explain }: { submissionId: string; explain: ReturnType<typeof useExplainFailure> }) {
  const [preview, setPreview] = useState<{ data: CoachPreview; submissionId: string } | null>(null);
  const [choices, setChoices] = useState<Record<"compile_output" | "failing_test", boolean>>({ compile_output: true, failing_test: true });
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<unknown>(null);
  const [changed, setChanged] = useState<string | null>(null);
  const [cancelled, setCancelled] = useState(false);

  async function check(next = choices) {
    setChecking(true);
    setCheckError(null);
    setCancelled(false);
    try {
      const data = await api.explainPreview({ submission_id: submissionId, share_compile_output: next.compile_output, share_failing_test: next.failing_test });
      setPreview({ data, submissionId });
      setChanged(null);
    } catch (e) {
      setCheckError(e);
    } finally {
      setChecking(false);
    }
  }

  function send() {
    if (!preview) return;
    explain.mutate(
      { submission_id: preview.submissionId, share_compile_output: choices.compile_output, share_failing_test: choices.failing_test,
        approved_context: preview.data.context_fingerprint },
      {
        onError: (e) => {
          if (e instanceof ApiError && e.code === "context_changed") {
            const now = (e.details as { preview?: CoachPreview } | undefined)?.preview;
            if (now) setPreview({ data: now, submissionId: preview.submissionId });
            setChanged(REFUSED);
            explain.reset();
          }
        },
      },
    );
  }

  if (preview) {
    return (
      <div className="explain-cta stack-sm">
        <CoachContext preview={preview.data} choices={choices} changed={changed}
          stale={preview.submissionId !== submissionId ? "A newer submission came in since this was checked: check again to explain that one." : null}
          busy={explain.isPending || checking}
          sendLabel={preview.data.already_answered ? "Show the explanation" : "Ask for the explanation"}
          onChoose={(key: ChoiceKey, send) => {
            if (key === "verdict") return;
            const next = { ...choices, [key]: send };
            setChoices(next);
            void check(next);
          }}
          onSend={send}
          onCancel={() => { setPreview(null); setChanged(null); setCancelled(true); }}
          onCheckAgain={() => void check()} />
        {!explain.isPending && <ActionError error={explain.error} action="The explanation" repeatSafe onRetry={send} />}
      </div>
    );
  }
  return (
    <div className="explain-cta">
      <Button size="sm" variant="secondary" loading={checking} onClick={() => void check()}>
        Explain this failure
      </Button>
      <span className="subtle">Uses the public tests and compiler output only. You'll see exactly what the coach will read first.</span>
      {cancelled && <p className="subtle" role="status">Cancelled. Nothing was sent.</p>}
      <InlineError error={checkError} />
    </div>
  );
}
