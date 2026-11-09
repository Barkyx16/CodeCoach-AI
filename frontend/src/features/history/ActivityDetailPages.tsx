import { Link, useNavigate, useParams } from "react-router-dom";

import { useAIHistoryItem, useSubmission } from "@/api/queries";
import type { CodeReview, FailureExplanation } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge, StatusBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/States";
import { PrivateUnavailable } from "@/components/Unavailable";
import { isGone } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { ReviewResult } from "@/features/workspace/CoachPanel";
import { FailureExplanationView } from "@/features/workspace/FailureExplanation";

/** One saved code submission: its verdict (only if the judge ran) and the code that was submitted. */
export function SubmissionDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const q = useSubmission(id);
  if (q.isPending) return <LoadingState label="Loading submission…" />;
  if (q.isError && isGone(q.error)) return <PrivateUnavailable what="submission" list={{ to: "/history?type=code_submission", label: "All submissions" }} />;
  if (q.isError) return <div className="page"><BackLink fallback={{ to: "/history", label: "History" }} /><ErrorState error={q.error} onRetry={() => q.refetch()} /></div>;
  const s = q.data;
  const judged = s.is_terminal && s.status !== "QUEUED" && s.status !== "RUNNING";
  return (
    <div className="page activity-detail">
      <BackLink fallback={{ to: "/history?type=code_submission", label: "All submissions" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">CODE SUBMISSION</p>
          <h1 className="page__title">{s.problem_title}</h1>
          <p className="page__subtitle">Submitted {formatDateTime(s.created_at)}</p>
        </div>
        <div className="row">
          <Link to={`/problems/${s.problem_slug}`} className="btn btn--secondary btn--md">Open the problem</Link>
          <Button variant="primary" onClick={() => navigate(`/problems/${s.problem_slug}`, { state: { loadCode: s.source_code, loadFrom: formatDateTime(s.created_at) } })}>
            Open this code in the editor…
          </Button>
        </div>
      </div>
      <Card className="stack">
        <h2 className="section-title">Result</h2>
        {judged ? (
          <>
            <p className="row"><StatusBadge status={s.status} />{s.result && <span className="subtle">{s.result.passed_count} of {s.result.total_count} tests passed</span>}</p>
            {s.result?.stderr_excerpt && <pre className="final-code">{s.result.stderr_excerpt}</pre>}
          </>
        ) : s.execution_enabled ? (
          <p>Waiting for the judge. This page updates when it finishes.</p>
        ) : (
          <p><Badge>Saved, not judged</Badge> The code judge isn't available on this server (it needs Linux with gVisor), so this attempt was saved without a verdict. It is not counted as passed or failed.</p>
        )}
      </Card>
      <Card className="stack">
        {s.starting_code != null && (
          <>
            <h2 className="section-title">Started from</h2>
            <p className="subtle">The debugging exercise's faulty code{s.lab_version != null ? ` (version ${s.lab_version})` : ""}, as it was when you made this attempt.</p>
            <pre className="final-code" tabIndex={0} aria-label="Starting code">{s.starting_code}</pre>
          </>
        )}
        <h2 className="section-title">Submitted code</h2>
        <pre className="final-code" tabIndex={0} aria-label="Submitted code">{s.source_code}</pre>
        <p className="subtle">Opening it in the editor asks before replacing your current draft.</p>
      </Card>
    </div>
  );
}

/** One saved hint, code review or failure explanation. */
export function CoachingDetailPage() {
  const { id = "" } = useParams();
  const q = useAIHistoryItem(id);
  if (q.isPending) return <LoadingState label="Loading feedback…" />;
  if (q.isError && isGone(q.error)) return <PrivateUnavailable what="feedback" list={{ to: "/history", label: "History" }} />;
  if (q.isError) return <div className="page"><BackLink fallback={{ to: "/history", label: "History" }} /><ErrorState error={q.error} onRetry={() => q.refetch()} /></div>;
  const item = q.data;
  const response = (item.response ?? {}) as Record<string, unknown>;
  const title = item.action === "hint" ? `Hint, level ${item.hint_level ?? "?"}` : item.action === "explain_failure" ? "Failure explanation" : "Code review";
  return (
    <div className="page activity-detail">
      <BackLink fallback={{ to: "/history?type=coaching", label: "All coaching" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">COACHING</p>
          <h1 className="page__title">{title}: {item.problem_title}</h1>
          <p className="page__subtitle">{formatDateTime(item.created_at)} · by {item.provider}</p>
        </div>
        <Link to={`/problems/${item.problem_slug}`} className="btn btn--secondary btn--md">Open the problem</Link>
      </div>
      <Card className="stack">
        {item.response === null ? (
          <p>This feedback's text wasn't saved, so it can't be shown again.</p>
        ) : item.action === "hint" ? (
          <p>{String(response.hint ?? "")}</p>
        ) : item.action === "explain_failure" ? (
          <FailureExplanationView data={{
            submission_id: "", status: "", cached: true, provider: item.provider,
            explanation: response as unknown as FailureExplanation,
            disclaimer: "Based only on the public tests and compiler output.",
          }} />
        ) : (
          <ReviewResult data={{
            review: response as unknown as CodeReview, provider: item.provider, expected_complexity: null,
            judge_status: null, disclaimer: "AI feedback can be wrong. Pass/fail comes only from the test judge.",
          }} />
        )}
      </Card>
    </div>
  );
}
