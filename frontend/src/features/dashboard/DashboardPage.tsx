import { Link } from "react-router-dom";

import { useAIUsage, useProgress, useRecommendations } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { DifficultyBadge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { percent, plural, timeAgo, titleCase } from "@/lib/format";

import { ActivityHeatmap } from "./ActivityHeatmap";
import { ProgressBars } from "./ProgressBars";

function StatTile({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <Card className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__value">{value}</span>
      {detail && <span className="subtle">{detail}</span>}
    </Card>
  );
}

const KIND_LABEL = { retry: "Finish it", weak_topic: "Weak spot", next_step: "Next step", interview: "Interview" } as const;

export function DashboardPage() {
  const { user } = useAuth();
  const progress = useProgress();
  const recs = useRecommendations(5);
  const usage = useAIUsage();

  if (progress.isPending) return <LoadingState label="Loading your progress…" />;
  if (progress.isError) return <div className="page"><ErrorState error={progress.error} onRetry={() => progress.refetch()} /></div>;
  const p = progress.data;
  const isNew = p.attempted === 0 && p.hints_used === 0 && p.reviews_requested === 0;

  return (
    <div className="page dashboard">
      <div className="page__header">
        <div>
          <h1 className="page__title">{user?.display_name ? `${user.display_name}'s progress` : "Your progress"}</h1>
          <p className="page__subtitle">{p.last_active_at ? `Last active ${timeAgo(p.last_active_at)}` : "No activity yet"}</p>
        </div>
      </div>

      <section className="stat-row" aria-label="Summary">
        <StatTile label="Solved" value={`${p.solved}`} detail={`of ${p.total_problems} problems`} />
        <StatTile label="Current streak" value={`${p.current_streak_days} ${p.current_streak_days === 1 ? "day" : "days"}`}
          detail={`Longest: ${p.longest_streak_days}`} />
        <StatTile label="Acceptance rate" value={percent(p.acceptance_rate)}
          detail={p.acceptance_rate === null ? "No judged submissions yet" : `${p.accepted_submissions} accepted`} />
        <StatTile label="Coaching used" value={`${p.hints_used + p.reviews_requested}`}
          detail={`${plural(p.hints_used, "hint")} · ${plural(p.reviews_requested, "review")}`} />
      </section>

      {isNew && (
        <EmptyState title="Your dashboard fills in as you practice" action={<Link to="/problems" className="btn btn--primary btn--md">Start a problem</Link>}>
          Open a problem, ask for a hint or submit an attempt, and your stats will show up here.
        </EmptyState>
      )}

      <div className="dashboard__grid">
        <Card className="stack">
          <h2 className="section-title">Activity</h2>
          <ActivityHeatmap days={p.activity} />
        </Card>

        <Card className="stack">
          <h2 className="section-title">Up next</h2>
          {recs.isPending ? <LoadingState /> : recs.isError ? <ErrorState error={recs.error} /> : (
            <ul className="rec-list">
              {recs.data.map((r) => (
                <li key={r.slug}>
                  <Link to={`/problems/${r.slug}`} className="rec">
                    <span className="row">
                      <strong>{r.title}</strong>
                      <DifficultyBadge difficulty={r.difficulty} />
                      <span className="badge">{KIND_LABEL[r.kind]}</span>
                    </span>
                    <span className="subtle">{r.reason}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {p.weakest_topics.length > 0 && (
            <p className="subtle">Focus areas: {p.weakest_topics.map(titleCase).join(", ")}</p>
          )}
        </Card>

        <Card className="stack">
          <h2 className="section-title">Solved by difficulty</h2>
          <ProgressBars showAttempted={false}
            rows={p.by_difficulty.map((d) => ({ key: d.difficulty, label: titleCase(d.difficulty), total: d.total_problems, solved: d.solved }))} />
        </Card>

        <Card className="stack">
          <h2 className="section-title">By topic</h2>
          <ProgressBars rows={p.by_topic.map((t) => ({ key: t.topic, label: titleCase(t.topic), total: t.total_problems, solved: t.solved, attempted: t.attempted }))} />
        </Card>
      </div>

      {usage.data && (
        <p className="subtle dashboard__usage">
          AI coach: {usage.data.used_today} of {usage.data.daily_limit} requests used in the last 24 hours ({usage.data.provider}).
        </p>
      )}
    </div>
  );
}
