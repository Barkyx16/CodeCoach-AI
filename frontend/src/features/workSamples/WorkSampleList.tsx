import { Link } from "react-router-dom";

import { useWorkSamples } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { Card } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/States";

/** /work-samples: briefs for a short professional artifact (Volume 10, prompt 5). Briefs for the
 * learner's career come first; the rest are open to anyone curious. Only these careers have one. */
export function WorkSampleList() {
  const { user } = useAuth();
  const briefs = useWorkSamples();
  const track = user?.career_track ?? "";
  return (
    <div className="page ws-list">
      <div className="page__header">
        <div>
          <p className="eyebrow">WORK SAMPLES</p>
          <h1 className="page__title">Practice the work, not only the interview</h1>
          <p className="page__subtitle">
            Each brief asks for a short piece of real-looking work (an incident update, a reply to a customer, a handoff note) from
            made-up facts. You get feedback on whether it covers what the brief asks, using only those facts.
          </p>
        </div>
      </div>
      {briefs.isPending ? <LoadingState label="Loading briefs…" />
        : briefs.isError ? <ErrorState error={briefs.error} onRetry={() => void briefs.refetch()} />
          : (() => {
            const mine = briefs.data.filter((b) => b.careers.includes(track));
            const others = briefs.data.filter((b) => !b.careers.includes(track));
            const list = (items: typeof briefs.data) => (
              <ul className="stack">
                {items.map((b) => (
                  <li key={b.id}>
                    <Card className="stack-sm">
                      <h3 className="section-title"><Link to={`/work-samples/${b.id}`}>{b.title}</Link></h3>
                      <p className="subtle">{b.format_label}</p>
                    </Card>
                  </li>
                ))}
              </ul>
            );
            return (
              <div className="stack">
                {mine.length > 0 ? <section className="stack-sm" aria-labelledby="ws-mine"><h2 className="section-title" id="ws-mine">For your career</h2>{list(mine)}</section>
                  : <p>There's no work-sample brief for your career yet. These are open to anyone curious.</p>}
                {others.length > 0 && <section className="stack-sm" aria-labelledby="ws-others"><h2 className="section-title" id="ws-others">{mine.length ? "Other careers" : "Briefs so far"}</h2>{list(others)}</section>}
              </div>
            );
          })()}
    </div>
  );
}
