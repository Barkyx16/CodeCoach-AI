import { Link } from "react-router-dom";

import { useTestDesigns } from "@/api/queries";
import { Card } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/States";

/** /problems?view=test-design: test-design exercises (Volume 10, prompt 4). */
export function TestDesignList() {
  const exercises = useTestDesigns();
  return (
    <div className="page td-list">
      <div className="page__header">
        <div>
          <p className="eyebrow">TEST DESIGN</p>
          <h1 className="page__title">Design tests that find bugs</h1>
          <p className="page__subtitle">
            Each exercise is a small specification with a trusted reference and a few faulty versions. Write cases, run them, and see
            which faulty versions each case tells apart. One well-placed case can do more than many ordinary ones.
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
                    <h2 className="section-title"><Link to={`/test-design/${e.slug}`}>{e.title}</Link></h2>
                    <p>{e.summary}</p>
                    <p className="subtle">{e.variant_count} faulty versions to tell apart.</p>
                  </Card>
                </li>
              ))}
            </ul>
          )}
    </div>
  );
}
