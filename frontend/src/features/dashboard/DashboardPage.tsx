import { Link } from "react-router-dom";

import { useAIUsage, useCareers, useProgress, useRecommendations } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { DifficultyBadge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { DEFAULT_TRACK } from "@/features/careers/practiceTrack";
import { ErrorState, LoadingState } from "@/components/States";
import { percent, plural, timeAgo, titleCase } from "@/lib/format";

import { ActivityHeatmap } from "./ActivityHeatmap";
import { CareerDashboard } from "./CareerDashboard";
import { TodayCard } from "@/features/plan/TodayCard";
import { OnboardingBanner } from "@/features/onboarding/OnboardingBanner";

import { ContinueCard } from "./ContinueCard";
import { EndedEarlyNote } from "./EndedEarlyNote";
import { MorePractice } from "./MorePractice";
import { ProgressBars } from "./ProgressBars";
import { RecentActivity } from "./RecentActivity";
import { StatTile } from "./StatTile";
import { Icon } from "@/components/Icon";

const KIND_LABEL = { retry: "Finish it", weak_topic: "Weak spot", next_step: "Next step", interview: "Interview" } as const;

/** The dashboard for the user's own career: coding progress for jobs with coding problems, else
 * progress on that career's interview questions. */
export function DashboardPage() {
  const { user } = useAuth();
  const careers = useCareers();
  const track = user?.career_track || DEFAULT_TRACK;
  const career = careers.data?.find((c) => c.slug === track);
  if (careers.isPending && track !== DEFAULT_TRACK) return <LoadingState label="Loading your progress…" />;
  const hasCoding = career ? career.has_coding : track === DEFAULT_TRACK;
  return hasCoding ? <CodingDashboard /> : <CareerDashboard track={track} careerTitle={career?.title} />;
}

function CodingDashboard() {
  const progress = useProgress();
  const recs = useRecommendations(5);
  const usage = useAIUsage();

  if (progress.isPending) return <LoadingState label="Loading your progress…" />;
  if (progress.isError) return <div className="page"><ErrorState error={progress.error} onRetry={() => progress.refetch()} /></div>;
  const p = progress.data;
  const isNew = p.attempted === 0 && p.hints_used === 0 && p.reviews_requested === 0;

  return (
    <div className="page dashboard">
      <div className="page__header dashboard__header">
        <div>
          <h1 className="page__title">Your interview practice</h1>
          <p className="page__subtitle">Coding problems · {p.last_active_at ? `last active ${timeAgo(p.last_active_at)}` : "no activity yet"}</p>
        </div>
        <Link to="/interviews" className="btn btn--secondary btn--md">Mock interview</Link>
      </div>

      <OnboardingBanner />
      <TodayCard />
      <ContinueCard />
      <EndedEarlyNote />

      <h2 className="dashboard__section-title">Your progress</h2>
      <section className="stat-row" aria-label="Summary">
        <StatTile icon="target" label="Solved" value={`${p.solved}`} detail={`of ${p.total_problems} problems`}
          fraction={p.total_problems ? p.solved / p.total_problems : 0} />
        <StatTile icon="flame" label="Current streak" value={`${p.current_streak_days} ${p.current_streak_days === 1 ? "day" : "days"}`}
          detail={`Longest: ${p.longest_streak_days}`} />
        <StatTile icon="chart" label="Acceptance rate" value={percent(p.acceptance_rate)}
          detail={p.acceptance_rate === null ? "No judged submissions yet" : `${p.accepted_submissions} accepted`} />
        <StatTile icon="spark" label="Coaching used" value={`${p.hints_used + p.reviews_requested}`}
          detail={`${plural(p.hints_used, "hint")} · ${plural(p.reviews_requested, "review")}`} />
      </section>

      {isNew && (
        <p className="dashboard-onboarding">
          <Icon name="code" size={16} aria-hidden="true" />
          <span>Your progress will appear as you practise. Open a problem, ask for a hint or submit an attempt, and your stats will show up here.{" "}
            <Link to="/problems">Start a problem <span aria-hidden="true">→</span></Link></span>
        </p>
      )}

      <MorePractice coding />

      {/* Two independent columns, so a short card never leaves a hole beside a tall one. */}
      <div className="dashboard__layout">
        <div className="dashboard__col">
          <Card className="stack">
            <div className="section-heading"><h2 className="section-title">Up next</h2><Link to="/problems">All problems <span aria-hidden="true">→</span></Link></div>
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

          <RecentActivity />

          <Card className="stack">
            <div className="section-heading"><h2 className="section-title">By topic</h2><Link to="/analytics">View all topics <span aria-hidden="true">→</span></Link></div>
            <ProgressBars rows={p.by_topic.slice(0, 6).map((t) => ({ key: t.topic, label: titleCase(t.topic), total: t.total_problems, solved: t.solved, attempted: t.attempted }))} />
            {p.by_topic.length > 6 && <p className="subtle">Showing 6 of {p.by_topic.length} topics. See Analytics for the full breakdown.</p>}
          </Card>
        </div>

        <div className="dashboard__col">
          <Card className="stack">
            <h2 className="section-title">Activity</h2>
            <ActivityHeatmap days={p.activity} />
          </Card>

          <Card className="stack">
            <h2 className="section-title">Solved by difficulty</h2>
            <ProgressBars showAttempted={false}
              rows={p.by_difficulty.map((d) => ({ key: d.difficulty, label: titleCase(d.difficulty), total: d.total_problems, solved: d.solved }))} />
          </Card>

          {usage.data && (
            <p className="subtle dashboard__usage">
              AI coach: {usage.data.used_today} of {usage.data.daily_limit} requests used in the last 24 hours ({usage.data.provider}).
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
