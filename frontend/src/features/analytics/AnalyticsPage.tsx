import { Link } from "react-router-dom";
import { useInterviews, useProgress, useRecommendations } from "@/api/queries";
import { Card } from "@/components/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { ActivityHeatmap } from "@/features/dashboard/ActivityHeatmap";
import { ProgressBars } from "@/features/dashboard/ProgressBars";
import { InterviewRow } from "@/features/interview/InterviewStartPage";
import { percent, titleCase } from "@/lib/format";

export default function AnalyticsPage() {
  const progress = useProgress();
  const interviews = useInterviews({ page: 1, page_size: 5 });
  const recommendations = useRecommendations(3);
  if (progress.isPending) return <LoadingState label="Loading practice insights…" />;
  if (progress.isError) return <div className="page"><ErrorState error={progress.error} onRetry={() => void progress.refetch()} /></div>;
  const p = progress.data;
  return <div className="page analytics">
    <div className="page__header"><div><p className="eyebrow">UNDERSTAND YOUR PRACTICE</p><h1 className="page__title">Analytics</h1><p className="page__subtitle">See where you are making progress, and choose what to work on next.</p></div><Link to="/problems" className="btn btn--primary btn--md">Keep practicing <span aria-hidden="true">→</span></Link></div>
    <section className="stat-row" aria-label="Practice statistics">
      <Metric label="Solved" value={`${p.solved} / ${p.total_problems}`} detail="Problems in the library" />
      <Metric label="Attempted" value={`${p.attempted}`} detail="Distinct problems" />
      <Metric label="Acceptance rate" value={percent(p.acceptance_rate)} detail={`${p.accepted_submissions} accepted submissions`} />
      <Metric label="Best streak" value={`${p.longest_streak_days} ${p.longest_streak_days === 1 ? "day" : "days"}`} detail={`${p.current_streak_days} ${p.current_streak_days === 1 ? "day" : "days"} in your current streak`} />
    </section>
    <p className="subtle analytics__scope">Statistics above cover all recorded practice. Activity below covers the last 28 days and includes problem opens, submissions, coaching and completed interviews.</p>
    {/* Main column: the long topic list and interviews; side column: short summaries. */}
    <div className="dashboard__layout">
      <div className="dashboard__col">
        <Card className="stack"><h2 className="section-title">Topic performance</h2><ProgressBars columns rows={p.by_topic.map((t) => ({ key: t.topic, label: titleCase(t.topic), total: t.total_problems, solved: t.solved, attempted: t.attempted }))} /></Card>
        <section className="card stack analytics__interviews" aria-label="Interview history"><div className="section-heading"><h2 className="section-title">Recent interviews</h2><Link to="/history?tab=interviews">View all interviews <span aria-hidden="true">→</span></Link></div>
          {interviews.isPending ? <LoadingState /> : interviews.isError ? <ErrorState error={interviews.error} onRetry={() => void interviews.refetch()} />
            : interviews.data.items.length === 0 ? <EmptyState title="A new perspective on your skills" action={<Link className="btn btn--secondary btn--md" to="/interviews">Start a mock interview</Link>}>Complete an interview to see your feedback here.</EmptyState>
            : <ul className="interview-list">{interviews.data.items.map((item) => <InterviewRow key={item.id} iv={item} />)}</ul>}
        </section>
      </div>
      <div className="dashboard__col">
        <Card className="stack"><h2 className="section-title">Your next focus</h2>
          {p.weakest_topics.length > 0 && <p className="muted">Topics to strengthen: {p.weakest_topics.map(titleCase).join(", ")}.</p>}
          {recommendations.isPending ? <LoadingState /> : recommendations.isError ? <ErrorState error={recommendations.error} onRetry={() => void recommendations.refetch()} />
            : recommendations.data.length === 0 ? <EmptyState title="No recommendations yet">Keep practicing to build your activity history.</EmptyState>
            : <ul className="rec-list">{recommendations.data.map((item) => <li key={item.slug}><Link to={`/problems/${item.slug}`} className="rec"><strong>{item.title}</strong><span className="subtle">{item.reason}</span></Link></li>)}</ul>}
        </Card>
        <Card className="stack"><h2 className="section-title">Solved by difficulty</h2><ProgressBars showAttempted={false} rows={p.by_difficulty.map((d) => ({ key: d.difficulty, label: titleCase(d.difficulty), total: d.total_problems, solved: d.solved }))} /></Card>
        <Card className="stack"><h2 className="section-title">Activity over time</h2><ActivityHeatmap days={p.activity} /></Card>
      </div>
    </div>
  </div>;
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <Card className="stat"><span className="stat__label">{label}</span><strong className="stat__value">{value}</strong><span className="subtle">{detail}</span></Card>;
}
