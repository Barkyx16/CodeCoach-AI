import { Link, useSearchParams } from "react-router-dom";

import { useLearnCatalog, useMyLearn } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { Badge } from "@/components/Badge";
import { Icon } from "@/components/Icon";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { DEFAULT_TRACK } from "@/features/careers/practiceTrack";

import { statusLabel } from "./progress";

/** Learn mode: short units for the chosen career, with honest coverage. `?career=` browses another
 * career without changing your profile. */
export function LearnPage() {
  const { user, isAuthenticated } = useAuth();
  const [params] = useSearchParams();
  const track = params.get("career") || user?.career_track || DEFAULT_TRACK;
  const catalog = useLearnCatalog(track);
  const mine = useMyLearn(track, isAuthenticated);

  if (catalog.isPending) return <LoadingState label="Loading lessons…" />;
  if (catalog.isError) return <div className="page"><ErrorState error={catalog.error} onRetry={() => void catalog.refetch()} /></div>;
  const c = catalog.data;
  const others = c.careers_with_units.filter((x) => x.track !== track);

  return (
    <div className="page learn-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">LEARN</p>
          <h1 className="page__title">{c.career_title} lessons</h1>
          <p className="page__subtitle">Short units that teach a skill before you're tested on it: an explanation, a worked example, common mistakes, a guided exercise and a quick check.</p>
        </div>
      </div>
      <p className="banner banner--info">{c.coverage_note}</p>
      {others.length > 0 && (
        <p className="subtle">
          Also available:{" "}
          {others.map((o, i) => (
            <span key={o.track}>{i > 0 && " · "}<Link to={`/learn?career=${o.track}`}>{o.title} ({o.units})</Link></span>
          ))}
        </p>
      )}
      {c.units.length === 0 ? (
        <EmptyState title={`No lessons for ${c.career_title} yet`} action={<Link className="btn btn--secondary btn--md" to="/problems?view=questions">Practice questions instead</Link>}>
          Practice questions and the plan still work for this career.
        </EmptyState>
      ) : (
        <ol className="learn-list">
          {c.units.map((u) => {
            const st = statusLabel(mine.data?.[u.id]);
            return (
              <li key={u.id} className="card learn-list__item">
                <div className="row learn-list__meta">
                  <span className="subtle"><Icon name="clock" size={13} /> {u.minutes} min</span>
                  {u.skill && <span className="subtle">Skill: {u.skill}</span>}
                  {isAuthenticated && <Badge tone={st.tone}>{st.text}</Badge>}
                  {u.review_status === "generated_draft" && <Badge tone="warning">Draft: not reviewed</Badge>}
                </div>
                <h2 className="section-title"><Link to={`/learn/${u.id}`}>{u.title}</Link></h2>
                <p>{u.objective}</p>
                {u.prerequisites.length > 0 && (
                  <p className="subtle">Before this: {u.prerequisites.map((p, i) => <span key={p.id}>{i > 0 && ", "}<Link to={`/learn/${p.id}`}>{p.title}</Link></span>)}</p>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
