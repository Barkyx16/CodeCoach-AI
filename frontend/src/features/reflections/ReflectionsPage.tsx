import { Link, useSearchParams } from "react-router-dom";

import { useReflections } from "@/api/queries";
import type { ReflectionOutcome } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

import { OUTCOME_LABEL } from "./labels";

/** Your private reflections on real interviews, searchable and filterable (the filters live in the URL). */
export function ReflectionsPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const outcome = (params.get("outcome") ?? "") as ReflectionOutcome | "";
  const archived = params.get("archived") !== "hide";
  const debounced = useDebouncedValue(q, 250);
  const list = useReflections({ q: debounced, outcome: outcome || undefined, include_archived: archived });
  const update = (k: string, v: string | null) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };
  return (
    <div className="page reflections-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">AFTER THE INTERVIEW · PRIVATE</p>
          <h1 className="page__title">Your interview reflections</h1>
          <p className="page__subtitle">What you noticed in real interviews, in your own words. Separate from practice scores and from any AI feedback; only you can see them.</p>
        </div>
      </div>
      <div className="row reflections-filters" role="search" aria-label="Filter your reflections">
        <label className="field"><span className="field__label">Search</span>
          <input className="input" type="search" value={q} onChange={(e) => update("q", e.target.value || null)} />
        </label>
        <label className="field"><span className="field__label">Outcome</span>
          <select className="select" value={outcome} onChange={(e) => update("outcome", e.target.value || null)}>
            <option value="">Any</option>
            {(Object.keys(OUTCOME_LABEL) as ReflectionOutcome[]).map((o) => <option key={o} value={o}>{OUTCOME_LABEL[o]}</option>)}
          </select>
        </label>
        <label className="checkbox"><input type="checkbox" checked={archived} onChange={(e) => update("archived", e.target.checked ? null : "hide")} />Include archived applications</label>
      </div>
      {list.isPending ? <LoadingState label="Loading reflections…" /> : list.isError ? <ErrorState error={list.error} onRetry={() => void list.refetch()} /> : list.data.length === 0 ? (
        <EmptyState title={q || outcome ? "Nothing matches" : "No reflections yet"}>
          {q || outcome ? "Try other words or clear the filters." : <>After a real interview, open it from <Link to="/applications">its application</Link> and choose “Reflect on this interview”.</>}
        </EmptyState>
      ) : (
        <ul className="stack">
          {list.data.map((r) => (
            <li key={r.event_id}>
              <Card className="stack-sm">
                <h2 className="section-title"><Link to={`/applications/${r.application_id}/events/${r.event_id}/reflection`} state={{ from: `/reflections?${params.toString()}`, fromLabel: "Back to your reflections" }}>{r.event_title}: {r.role_title} at {r.employer}</Link></h2>
                <p className="row subtle">
                  {r.event_on && <span>{r.event_on}</span>}
                  <Badge>{OUTCOME_LABEL[r.outcome]}</Badge>
                  {r.application_archived && <Badge>Archived application</Badge>}
                  {r.open_actions > 0 && <span>{r.open_actions} suggested {r.open_actions === 1 ? "step" : "steps"} to review</span>}
                </p>
                {r.topics.length > 0 && <p className="subtle">Topics: {r.topics.join(", ")}</p>}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
