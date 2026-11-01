import { Link } from "react-router-dom";

import { useAIUsage, useProgress, useRecommendations } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { DifficultyBadge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/States";
import { percent, plural, timeAgo, titleCase } from "@/lib/format";

import { ActivityHeatmap } from "./ActivityHeatmap";
import { ProgressBars } from "./ProgressBars";
import { RecentActivity } from "./RecentActivity";
import { CompletionCard } from "./CompletionCard";
import { Icon, type IconName } from "@/components/Icon";

function StatTile({ label, value, detail, icon }: { label: string; value: string; detail?: string; icon: IconName }) {
  return (
    <Card className="stat">
      <Icon className="stat__icon" name={icon} size={19} />
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
          <p className="eyebrow">YOUR PRACTICE, IN PERSPECTIVE</p>
          <h1 className="page__title">{user?.display_name ? `${user.display_name}'s progress` : "Your progress"}</h1>
          <p className="page__subtitle">{p.last_active_at ? `Last active ${timeAgo(p.last_active_at)}` : "No activity yet"}</p>
        </div>
        <div className="row dashboard__actions"><Link to="/interviews" className="btn btn--secondary btn--md">Start a mock interview</Link><Link to="/problems" className="btn btn--primary btn--md">Practice now <span aria-hidden="true">→</span></Link></div>
      </div>

      <section className="stat-row" aria-label="Summary">
        <StatTile icon="target" label="Solved" value={`${p.solved}`} detail={`of ${p.total_problems} problems`} />
        <StatTile icon="flame" label="Current streak" value={`${p.current_streak_days} ${p.current_streak_days === 1 ? "day" : "days"}`}
          detail={`Longest: ${p.longest_streak_days}`} />
        <StatTile icon="chart" label="Acceptance rate" value={percent(p.acceptance_rate)}
          detail={p.acceptance_rate === null ? "No judged submissions yet" : `${p.accepted_submissions} accepted`} />
        <StatTile icon="spark" label="Coaching used" value={`${p.hints_used + p.reviews_requested}`}
          detail={`${plural(p.hints_used, "hint")} · ${plural(p.reviews_requested, "review")}`} />
      </section>
      <CompletionCard solved={p.solved} total={p.total_problems} />

      {isNew && (
        <div className="dashboard-onboarding"><span className="icon-tile"><Icon name="code" /></span><div><strong>Your dashboard fills in as you practice</strong><p className="subtle">Open a problem, ask for a hint or submit an attempt, and your stats will show up here.</p></div><Link to="/problems" className="btn btn--secondary btn--md">Start a problem <Icon name="arrow" size={15} /></Link></div>
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
              {recs.data.slice(0, 3).map((r) => (
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
          <div className="section-heading"><h2 className="section-title">By topic</h2><Link to="/analytics">View all topics <span aria-hidden="true">→</span></Link></div>
          <ProgressBars rows={p.by_topic.slice(0, 5).map((t) => ({ key: t.topic, label: titleCase(t.topic), total: t.total_problems, solved: t.solved, attempted: t.attempted }))} />
          {p.by_topic.length > 5 && <p className="subtle">Showing 5 of {p.by_topic.length} topics. See Analytics for the full breakdown.</p>}
        </Card>
      </div>
      <RecentActivity />

      {usage.data && (
        <p className="subtle dashboard__usage">
          AI coach: {usage.data.used_today} of {usage.data.daily_limit} requests used in the last 24 hours ({usage.data.provider}).
        </p>
      )}
    </div>
  );
}
