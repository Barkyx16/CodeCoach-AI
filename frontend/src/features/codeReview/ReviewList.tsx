import { Link } from "react-router-dom";

import { useReviewExercises } from "@/api/queries";
import { DifficultyBadge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/States";

/** /problems?view=code-review: code-review exercises (Volume 10, prompt 3). The learner reviews
 * someone else's code, then compares with an authored review. Nothing says which exercises have a
 * defect: one of them has none. */
export function ReviewList() {
  const exercises = useReviewExercises();
  return (
    <div className="page review-list">
      <div className="page__header">
        <div>
          <p className="eyebrow">CODE REVIEW</p>
          <h1 className="page__title">Review someone else's code</h1>
          <p className="page__subtitle">
            Each exercise is a short solution someone else wrote for one of the coding problems. Write your findings, then compare them
            with an authored review. Not every exercise has a bug: saying so is a good review too.
          </p>
          <p><Link to="/problems">Back to the coding problems</Link></p>
        </div>
      </div>
      {exercises.isPending ? <LoadingState label="Loading exercises…" />
        : exercises.isError ? <ErrorState error={exercises.error} onRetry={() => void exercises.refetch()} />
          : (
            <ul className="stack">
              {exercises.data.map((e) => (
                <li key={e.slug}>
                  <Card className="stack-sm">
                    <h2 className="section-title"><Link to={`/code-reviews/${e.slug}`}>{e.title}</Link></h2>
                    <p>A teammate's solution to {e.problem_title}.</p>
                    <p className="row"><DifficultyBadge difficulty={e.difficulty} /></p>
                  </Card>
                </li>
              ))}
            </ul>
          )}
    </div>
  );
}
