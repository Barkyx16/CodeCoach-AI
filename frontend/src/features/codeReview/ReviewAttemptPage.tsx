import { Link, useParams } from "react-router-dom";

import { useReviewAttempt } from "@/api/queries";
import type { ReviewFeedback } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { ErrorState, LoadingState } from "@/components/States";
import { formatDateTime } from "@/lib/format";

import { CodeView, ComparisonView } from "./Comparison";

/** /code-reviews/attempts/:id: one sent review, with the code and authored review it was compared
 * with as they were then, whatever the exercise says now. */
export function ReviewAttemptPage() {
  const { attemptId = "" } = useParams();
  const attempt = useReviewAttempt(attemptId);
  if (attempt.isPending) return <LoadingState label="Loading your review…" />;
  if (attempt.isError) return <div className="page"><ErrorState error={attempt.error} onRetry={() => void attempt.refetch()} /></div>;
  const a = attempt.data;
  return (
    <div className="page review-page">
      <BackLink fallback={{ to: `/code-reviews/${a.slug}`, label: a.title }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">CODE REVIEW · YOUR REVIEW</p>
          <h1 className="page__title">{a.title}</h1>
          <p className="page__subtitle">Sent {formatDateTime(a.created_at)}, reviewing version {a.exercise_version} of the exercise.</p>
        </div>
      </div>
      {a.current_version !== a.exercise_version && (
        <p className="banner banner--info" role="note">
          {a.current_version == null ? "This exercise is no longer offered." : `The exercise is version ${a.current_version} now.`} This review is
          shown with the code and the authored review it was compared with then.
        </p>
      )}
      <h2 className="section-title">The code you reviewed</h2>
      <CodeView code={a.code} label={`The code you reviewed (version ${a.exercise_version}), with line numbers`} />
      <ComparisonView findings={a.findings} summary={a.summary} feedback={a.feedback as unknown as ReviewFeedback}
        reference={a.reference} afterReveal={a.after_reveal} />
      {a.current_version != null && <p><Link to={`/code-reviews/${a.slug}`}>Open the exercise</Link></p>}
    </div>
  );
}
