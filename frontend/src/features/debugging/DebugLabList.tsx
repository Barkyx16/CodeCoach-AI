import { Link } from "react-router-dom";

import { useProblems } from "@/api/queries";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/States";

/** /problems?view=debugging: the debugging lab's exercises (Volume 10, prompt 2). Each opens in the
 * usual coding workspace, starting from the faulty code. */
export function DebugLabList() {
  const exercises = useProblems({ kind: "debug", page_size: 50 });
  return (
    <div className="page debug-lab">
      <div className="page__header">
        <div>
          <p className="eyebrow">DEBUGGING LAB</p>
          <h1 className="page__title">Fix a broken program</h1>
          <p className="page__subtitle">
            Each exercise starts from code with a known defect. Reproduce it with the public cases, work out the cause, and fix it.
            Any fix that passes the tests counts; the explanation and one repair are there when you ask.
          </p>
          <p><Link to="/problems">Back to the coding problems</Link></p>
        </div>
      </div>
      {exercises.isPending ? <LoadingState label="Loading exercises…" />
        : exercises.isError ? <ErrorState error={exercises.error} onRetry={() => void exercises.refetch()} />
          : (
            <ul className="stack">
              {exercises.data.items.map((e) => (
                <li key={e.slug}>
                  <Card className="stack-sm">
                    <h2 className="section-title"><Link to={`/problems/${e.slug}`}>{e.title}</Link></h2>
                    <p>{e.summary}</p>
                    <p className="row"><Badge>{e.difficulty}</Badge>{e.topics.filter((t) => t !== "debugging").map((t) => <Badge key={t} tone="neutral">{t}</Badge>)}</p>
                  </Card>
                </li>
              ))}
            </ul>
          )}
    </div>
  );
}
