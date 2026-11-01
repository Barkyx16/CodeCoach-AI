import type { Submission } from "@/api/types";
import { StatusBadge } from "@/components/Badge";
import { Spinner } from "@/components/Spinner";
import { ErrorState } from "@/components/States";
import { formatArgs, formatValue, timeAgo } from "@/lib/format";

const STATUS_COPY: Partial<Record<Submission["status"], string>> = {
  PASSED: "All tests passed. Nice work.",
  FAILED: "Some tests failed. Check the cases below.",
  COMPILE_ERROR: "Your code didn't compile.",
  RUNTIME_ERROR: "Your code threw an exception while running.",
  TIME_LIMIT: "Your code ran too long. Look for an infinite loop or a slower-than-needed approach.",
  MEMORY_LIMIT: "Your code used too much memory.",
  INTERNAL_ERROR: "The judge had a problem. This wasn't your fault; try again.",
};

export function SubmissionPanel({ submission, error }: { submission: Submission | undefined; error: unknown }) {
  if (error) return <ErrorState error={error} />;
  if (!submission) {
    return (
      <div className="results results--empty">
        <p className="muted">Submit your solution to save an attempt. <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd></p>
      </div>
    );
  }
  const running = !submission.is_terminal && submission.execution_enabled;
  const result = submission.result;
  return (
    <div className="results" aria-live="polite">
      <div className="results__header">
        <StatusBadge status={submission.status} />
        {running && <Spinner size="sm" label="Judging" />}
        <span className="subtle">Submitted {timeAgo(submission.created_at)}</span>
      </div>

      {!submission.execution_enabled && (
        <div className="banner" role="status">
          <strong>Saved, but not run yet.</strong> {submission.status_detail}
          <div className="subtle">Meanwhile, ask the AI coach for a review of this code.</div>
        </div>
      )}

      {submission.is_terminal && STATUS_COPY[submission.status] && (
        <p className={submission.status === "PASSED" ? "results__verdict results__verdict--pass" : "results__verdict"}>
          {STATUS_COPY[submission.status]}
        </p>
      )}

      {result && (
        <>
          <div className="results__stats">
            <span><strong>{result.passed_count}</strong>/{result.total_count} tests passed</span>
            {result.runtime_ms !== null && <span className="subtle">{result.runtime_ms} ms</span>}
            {result.memory_kb !== null && <span className="subtle">{Math.round(result.memory_kb / 1024)} MB</span>}
          </div>
          <ul className="case-list">
            {result.public_results.map((r) => (
              <li key={r.index} className={`case case--${r.passed ? "pass" : "fail"}`}>
                <span className="case__icon" aria-label={r.passed ? "passed" : "failed"}>{r.passed ? "✓" : "✗"}</span>
                <span>
                  {r.input && <code>{formatArgs(r.input)}</code>}
                  {!r.passed && (
                    <span className="case__detail">
                      expected <code>{formatValue(r.expected_output)}</code>, got{" "}
                      <code>{r.exception ? `exception ${r.exception}` : formatValue(r.actual_output)}</code>
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
          {result.stderr_excerpt && <pre className="stderr">{result.stderr_excerpt}</pre>}
        </>
      )}
    </div>
  );
}
