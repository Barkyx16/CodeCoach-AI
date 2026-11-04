import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useScenario, useScenarioAttempts, useScenarios } from "@/api/queries";
import type { ScenarioSummary } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Icon } from "@/components/Icon";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";
import { DEFAULT_TRACK } from "@/features/careers/practiceTrack";
import { timeAgo } from "@/lib/format";
import { externalHref } from "@/lib/links";

function Facts({ s }: { s: ScenarioSummary }) {
  return (
    <p className="row scenario-facts">
      <span className="subtle"><Icon name="clock" size={13} /> about {s.minutes} min (author's estimate)</span>
      <span className="subtle">{s.decisions} decisions · {s.endings} possible endings</span>
      <span className="subtle">Version {s.version}</span>
      {s.regulated && <Badge tone="warning">Not clinically validated</Badge>}
    </p>
  );
}

/** Scenarios for a career, with honest coverage. `?career=` browses another career. */
export function ScenariosPage() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const track = params.get("career") || user?.career_track || DEFAULT_TRACK;
  const catalog = useScenarios(track);
  if (catalog.isPending) return <LoadingState label="Loading scenarios…" />;
  if (catalog.isError) return <div className="page"><ErrorState error={catalog.error} onRetry={() => void catalog.refetch()} /></div>;
  const c = catalog.data;
  const others = c.careers_with_scenarios.filter((x) => x.track !== track);
  return (
    <div className="page scenarios-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">SCENARIOS</p>
          <h1 className="page__title">{c.career_title} scenarios</h1>
          <p className="page__subtitle">Fictional situations where your choices change what happens next, with a debrief on the path you took.</p>
        </div>
      </div>
      <p className="banner banner--info">{c.coverage_note}</p>
      {others.length > 0 && (
        <p className="subtle">Also available: {others.map((o, i) => <span key={o.track}>{i > 0 && " · "}<Link to={`/scenarios?career=${o.track}`}>{o.title} ({o.scenarios})</Link></span>)}</p>
      )}
      {c.scenarios.length === 0 ? (
        <EmptyState title={`No scenarios for ${c.career_title} yet`} action={<Link className="btn btn--secondary btn--md" to="/interviews">Try a mock interview</Link>}>
          Mock interviews and practice questions still cover this career.
        </EmptyState>
      ) : (
        <ul className="learn-list">
          {c.scenarios.map((s) => (
            <li key={s.id} className="card learn-list__item">
              <h2 className="section-title"><Link to={`/scenarios/${s.id}`}>{s.title}</Link></h2>
              <p><strong>You are:</strong> {s.role}. <strong>Goal:</strong> {s.objective}</p>
              <Facts s={s} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The briefing before starting: role, goal, time, scope, how choices work, and your attempts. */
export function ScenarioBriefing() {
  const { id = "" } = useParams();
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const scenario = useScenario(id);
  const attempts = useScenarioAttempts(id, isAuthenticated);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  if (scenario.isPending) return <LoadingState label="Loading scenario…" />;
  if (scenario.isError) return <div className="page"><ErrorState error={scenario.error} onRetry={() => void scenario.refetch()} /></div>;
  const s = scenario.data;
  const ongoing = attempts.data?.find((a) => a.status === "in_progress" && a.mode === "assessed" && !a.retired);

  async function begin() {
    setBusy(true);
    setError(null);
    try {
      const a = await api.startScenario(s.id, { mode: "assessed" });
      navigate(`/scenarios/attempts/${a.id}`);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  return (
    <div className="page scenario-briefing">
      <BackLink fallback={{ to: `/scenarios?career=${s.track}`, label: `${s.career_title} scenarios` }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">SCENARIO · {s.career_title.toUpperCase()}</p>
          <h1 className="page__title">{s.title}</h1>
          <Facts s={s} />
        </div>
      </div>
      <div className="note-page__layout">
        <div className="stack">
          <Card className="stack-sm">
            <h2 className="section-title">Before you start</h2>
            <dl className="scenario-brief">
              <dt>Your role</dt><dd>{s.role}</dd>
              <dt>Your goal</dt><dd>{s.objective}</dd>
              <dt>Time</dt><dd>About {s.minutes} minutes (the author's estimate)</dd>
              <dt>Scope</dt><dd>{s.scope}</dd>
            </dl>
            <ul className="mini-list">
              <li>Information is revealed as the situation unfolds.</li>
              <li>Each choice is final for this attempt; the debrief shows what you chose and the alternatives.</li>
              <li>Your place is saved on the server, so you can leave and resume.</li>
              <li>Afterwards you can try another approach as a separate attempt; your first one is kept.</li>
            </ul>
            {isAuthenticated ? (
              <span className="row">
                <Button variant="primary" loading={busy} onClick={() => void begin()}>{ongoing ? "Resume your attempt" : "Start the scenario"}</Button>
              </span>
            ) : <p className="subtle"><Link to="/login" state={{ from: `/scenarios/${s.id}` }}>Sign in</Link> or try as a guest to play; your choices are saved to your account.</p>}
            <InlineError error={error} />
          </Card>
        </div>
        <aside className="stack">
          <Card className="stack-sm">
            <h2 className="section-title">Review and sources</h2>
            <p className="subtle">{s.review.note} ({s.review.by}, {s.review.on})</p>
            <ul className="learn-refs">
              {s.references.map((r) => (
                <li key={r.title}>
                  {externalHref(r.url) ? <a href={externalHref(r.url)} target="_blank" rel="noopener noreferrer">{r.title}</a> : <span>{r.title}</span>}
                  <span className="subtle"> · {r.publisher}</span>
                  {r.note && <span className="subtle learn-refs__note">{r.note}</span>}
                </li>
              ))}
            </ul>
          </Card>
          {attempts.data && attempts.data.length > 0 && (
            <Card className="stack-sm">
              <h2 className="section-title">Your attempts</h2>
              <ul className="mini-list">
                {attempts.data.map((a) => (
                  <li key={a.id}>
                    <Link to={`/scenarios/attempts/${a.id}`}>{a.status === "completed" ? a.outcome : "In progress"}</Link>
                    <span className="subtle"> · {a.mode === "exploration" ? "exploration · " : ""}v{a.version}{a.retired ? " (older version)" : ""} · {timeAgo(a.created_at)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}
