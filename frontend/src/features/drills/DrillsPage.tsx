import { Link } from "react-router-dom";

import { useDrills } from "@/api/queries";
import { Card } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/States";

/** Short communication drills to do between full mock interviews. */
export function DrillsPage() {
  const drills = useDrills();
  return (
    <div className="page drills-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">DRILLS</p>
          <h1 className="page__title">Communication drills</h1>
          <p className="page__subtitle">A few minutes each: one clear objective, your own words (spoken or typed), and feedback on what's in them. There are no streaks, rankings or speed scores.</p>
        </div>
      </div>
      {drills.isPending ? <LoadingState label="Loading drills…" /> : drills.isError ? <ErrorState error={drills.error} onRetry={() => void drills.refetch()} /> : (
        <ul className="stack">
          {drills.data.map((d) => (
            <li key={d.id}>
              <Card className="stack-sm">
                <h2 className="section-title"><Link to={`/drills/${d.id}`}>{d.title}</Link></h2>
                <p>{d.objective}</p>
                <p className="subtle">{d.attempts === 0 ? "Not tried yet" : `${d.attempts} ${d.attempts === 1 ? "attempt" : "attempts"}`}</p>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
