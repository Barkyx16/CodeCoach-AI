import { Link, useSearchParams } from "react-router-dom";

import { useActivityFacets, useCareers, useInterviews, useProgress, useRecommendations } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { Card } from "@/components/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { ActivityHeatmap } from "@/features/dashboard/ActivityHeatmap";
import { ProgressBars } from "@/features/dashboard/ProgressBars";
import { DEFAULT_TRACK } from "@/features/careers/practiceTrack";
import { InterviewRow } from "@/features/interview/InterviewStartPage";
import { percent, titleCase } from "@/lib/format";

import { CareerAnalyticsView } from "./CareerAnalyticsView";

const RANGES = [
  { id: "30", label: "Last 30 days", days: 30 },
  { id: "90", label: "Last 90 days", days: 90 },
  { id: "365", label: "Last 12 months", days: 365 },
  { id: "all", label: "All time", days: null },
] as const;

function sinceFor(days: number | null): string | undefined {
  if (days === null) return undefined;
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - (days - 1));
  return d.toISOString().slice(0, 10);
}

/**
 * Analytics for one career at a time: coding problems, or a career's interview questions. Any
 * career you've practised can be inspected without changing your career setting.
 */
export default function AnalyticsPage() {
  const { user } = useAuth();
  const careers = useCareers();
  const facets = useActivityFacets();
  const [params, setParams] = useSearchParams();
  const own = user?.career_track || DEFAULT_TRACK;
  const ownHasCoding = careers.data?.find((c) => c.slug === own)?.has_coding ?? own === DEFAULT_TRACK;
  const career = params.get("career") || (ownHasCoding ? "coding" : own);
  const range = RANGES.find((r) => r.id === params.get("range")) ?? RANGES[1];

  const options = new Map<string, string>();
  if (ownHasCoding) options.set("coding", "Coding problems");
  options.set(own, careers.data?.find((c) => c.slug === own)?.title ?? titleCase(own));
  for (const c of facets.data?.careers ?? []) options.set(c.value, c.label);
  if (!options.has(career)) options.set(career, careers.data?.find((c) => c.slug === career)?.title ?? titleCase(career));

  const set = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) next.set(k, v);
    setParams(next, { replace: true });
  };

  return (
    <div className="page analytics">
      <div className="page__header">
        <div>
          <p className="eyebrow">UNDERSTAND YOUR PRACTICE</p>
          <h1 className="page__title">Analytics</h1>
          <p className="page__subtitle">Built only from what you've recorded. Each career is shown on its own, never mixed with another.</p>
        </div>
        <Link to="/problems" className="btn btn--primary btn--md">Keep practising <span aria-hidden="true">→</span></Link>
      </div>
      <div className="analytics-filters" role="group" aria-label="Analytics scope">
        <label className="field">
          <span className="field__label">Career</span>
          <select className="select" value={career} onChange={(e) => set({ career: e.target.value })}>
            {[...options].map(([value, label]) => <option key={value} value={value}>{label}{value === own ? " (your career)" : ""}</option>)}
          </select>
        </label>
        {career !== "coding" && (
          <label className="field">
            <span className="field__label">Date range</span>
            <select className="select" value={range.id} onChange={(e) => set({ range: e.target.value })}>
              {RANGES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
          </label>
        )}
        {career !== own && career !== "coding" && <p className="subtle analytics-filters__note">Viewing {options.get(career)}. Your career setting is unchanged.</p>}
      </div>
      {career === "coding"
        ? <CodingAnalytics />
        : <CareerAnalyticsView key={career} track={career} since={sinceFor(range.days)} rangeLabel={range.label.toLowerCase()} />}
    </div>
  );
}

function CodingAnalytics() {
  const progress = useProgress();
  const interviews = useInterviews({ page: 1, page_size: 5 });
  const recommendations = useRecommendations(3);
  if (progress.isPending) return <LoadingState label="Loading practice insights…" />;
  if (progress.isError) return <ErrorState error={progress.error} onRetry={() => void progress.refetch()} />;
  const p = progress.data;
  return <>
    <section className="stat-row" aria-label="Practice statistics">
      <Metric label="Solved" value={`${p.solved} / ${p.total_problems}`} detail="Problems in the library" />
      <Metric label="Attempted" value={`${p.attempted}`} detail="Distinct problems" />
      <Metric label="Acceptance rate" value={percent(p.acceptance_rate)} detail={p.acceptance_rate === null ? "Not evaluated: no judged submissions yet" : `${p.accepted_submissions} accepted submissions`} />
      <Metric label="Best streak" value={`${p.longest_streak_days} ${p.longest_streak_days === 1 ? "day" : "days"}`} detail={`${p.current_streak_days} ${p.current_streak_days === 1 ? "day" : "days"} in your current streak`} />
    </section>
    <p className="subtle analytics__scope">Statistics above cover all recorded coding practice. Acceptance counts only submissions the judge evaluated; saved-but-not-judged attempts aren't counted as passed or failed. Activity below covers the last 28 days.</p>
    <div className="dashboard__layout">
      <div className="dashboard__col">
        <Card className="stack"><h2 className="section-title">Topic performance</h2><ProgressBars columns rows={p.by_topic.map((t) => ({ key: t.topic, label: titleCase(t.topic), total: t.total_problems, solved: t.solved, attempted: t.attempted }))} /></Card>
        <section className="card stack analytics__interviews" aria-label="Interview history"><div className="section-heading"><h2 className="section-title">Recent interviews</h2><Link to="/history?type=interview">View all interviews <span aria-hidden="true">→</span></Link></div>
          {interviews.isPending ? <LoadingState /> : interviews.isError ? <ErrorState error={interviews.error} onRetry={() => void interviews.refetch()} />
            : interviews.data.items.length === 0 ? <EmptyState title="A new perspective on your skills" action={<Link className="btn btn--secondary btn--md" to="/interviews">Start a mock interview</Link>}>Complete an interview to see your feedback here.</EmptyState>
            : <ul className="interview-list">{interviews.data.items.map((item) => <InterviewRow key={item.id} iv={item} />)}</ul>}
        </section>
      </div>
      <div className="dashboard__col">
        <Card className="stack"><h2 className="section-title">Your next focus</h2>
          {p.weakest_topics.length > 0 && <p className="muted">Topics to strengthen: {p.weakest_topics.map(titleCase).join(", ")}.</p>}
          {recommendations.isPending ? <LoadingState /> : recommendations.isError ? <ErrorState error={recommendations.error} onRetry={() => void recommendations.refetch()} />
            : recommendations.data.length === 0 ? <EmptyState title="No recommendations yet">Keep practising to build your activity history.</EmptyState>
            : <ul className="rec-list">{recommendations.data.map((item) => <li key={item.slug}><Link to={`/problems/${item.slug}`} className="rec"><strong>{item.title}</strong><span className="subtle">{item.reason}</span></Link></li>)}</ul>}
        </Card>
        <Card className="stack"><h2 className="section-title">Solved by difficulty</h2><ProgressBars showAttempted={false} rows={p.by_difficulty.map((d) => ({ key: d.difficulty, label: titleCase(d.difficulty), total: d.total_problems, solved: d.solved }))} /></Card>
        <Card className="stack"><h2 className="section-title">Activity over time</h2><ActivityHeatmap days={p.activity} /></Card>
      </div>
    </div>
  </>;
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <Card className="stat"><span className="stat__label">{label}</span><strong className="stat__value">{value}</strong><span className="subtle">{detail}</span></Card>;
}
