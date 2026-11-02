import { Link } from "react-router-dom";

import { useCareerAnalytics } from "@/api/queries";
import type { CareerAnalytics } from "@/api/types";
import { Card } from "@/components/Card";
import { WeeklyBars, type BarPoint } from "@/components/charts/WeeklyBars";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { ProgressBars } from "@/features/dashboard/ProgressBars";
import { StatTile } from "@/features/dashboard/StatTile";

function weekStart(day: string): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
  return d.toISOString().slice(0, 10);
}

function weekLabel(iso: string): string {
  return `Week of ${new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" })}`;
}

/** Every week in the range, so empty weeks show as gaps rather than disappearing. */
function weeks(a: CareerAnalytics): string[] {
  if (a.by_day.length === 0) return [];
  const out: string[] = [];
  const d = new Date(`${weekStart(a.by_day[0]!.day)}T00:00:00Z`);
  const end = weekStart(a.by_day.at(-1)!.day);
  while (d.toISOString().slice(0, 10) <= end) {
    out.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() + 7);
  }
  return out;
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Analytics for one career's questions, over a chosen range. Only recorded answers and rounds count. */
export function CareerAnalyticsView({ track, since, rangeLabel }: { track: string; since: string | undefined; rangeLabel: string }) {
  const q = useCareerAnalytics(track, since);
  if (q.isPending) return <LoadingState label="Loading analytics…" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const a = q.data;
  const iv = a.interviews;
  const allWeeks = weeks(a);
  const perWeek = new Map<string, number>();
  for (const d of a.by_day) perWeek.set(weekStart(d.day), (perWeek.get(weekStart(d.day)) ?? 0) + d.answers);
  const answerPoints: BarPoint[] = allWeeks.map((w) => {
    const n = perWeek.get(w) ?? 0;
    return { key: w, label: weekLabel(w), value: n, detail: `${weekLabel(w)}: ${n} ${n === 1 ? "answer" : "answers"}` };
  });
  const practised = a.skills.filter((s) => s.questions_answered > 0);

  if (a.answers === 0 && iv.completed + iv.abandoned + iv.expired + iv.in_progress === 0) {
    return (
      <EmptyState title={`No ${a.career_title} practice ${since ? "in this range" : "yet"}`}
        action={<span className="row"><Link className="btn btn--primary btn--md" to={`/problems?career=${track}&view=questions`}>Answer a question</Link><Link className="btn btn--secondary btn--md" to="/interviews/questions">Start a mock interview</Link></span>}>
        Analytics come from answers you submit and interviews you take. {since ? "Choose “All time” to include older practice." : "Answer a question to see your first results."}
      </EmptyState>
    );
  }

  return (
    <div className="stack">
      <section className="stat-row" aria-label={`${a.career_title} summary, ${rangeLabel}`}>
        <StatTile icon="target" label="Questions practised" value={`${a.questions_practiced}`} detail={`of ${a.total_questions} questions`}
          fraction={a.total_questions ? a.questions_practiced / a.total_questions : 0} />
        <StatTile icon="chart" label="Answers" value={`${a.answers}`} detail="Including repeats and interview answers" />
        <StatTile icon="spark" label="Strong questions" value={`${a.strong_questions}`} detail="Best score 85 or more" />
        <StatTile icon="clock" label="Interviews completed" value={`${iv.completed}`}
          detail={[iv.abandoned && `${iv.abandoned} ended early`, iv.expired && `${iv.expired} ran out of time`, iv.in_progress && `${iv.in_progress} in progress`].filter(Boolean).join(" · ") || "Question rounds"} />
      </section>

      <div className="dashboard__layout">
        <div className="dashboard__col">
          <Card className="stack">
            <h2 className="section-title">Skills covered</h2>
            <p className="subtle">{practised.length} of {a.skills.length} skills practised. Bars show how many of each skill's questions you've answered.</p>
            <ProgressBars columns showAttempted={false} unit="questions answered"
              rows={a.skills.map((s) => ({ key: s.skill, label: cap(s.skill), total: s.total_questions, solved: s.questions_answered }))} />
            <details>
              <summary>Exact values and scores</summary>
              <table className="data-table">
                <thead><tr><th scope="col">Skill</th><th scope="col">Questions answered</th><th scope="col">Answers</th><th scope="col">Average best score</th></tr></thead>
                <tbody>{a.skills.map((s) => (
                  <tr key={s.skill}><td>{cap(s.skill)}</td><td>{s.questions_answered} of {s.total_questions}</td><td>{s.answers}</td>
                    <td>{s.average_best_score === null ? "Not practised yet" : `${s.average_best_score}/100`}</td></tr>
                ))}</tbody>
              </table>
            </details>
          </Card>
          <Card className="stack">
            <WeeklyBars title="Answers per week" points={answerPoints} max={Math.max(...answerPoints.map((p) => p.value ?? 0), 1)}
              unit="Answers" emptyText="No answers in this range." />
          </Card>
        </div>
        <div className="dashboard__col">
          {a.trends.length === 0 ? (
            <Card className="stack"><h2 className="section-title">Score trend</h2><p className="subtle">Not evaluated yet: no answers in this range.</p></Card>
          ) : a.trends.map((t) => {
            const byWeek = new Map(t.points.map((p) => [p.week_start, p]));
            const points: BarPoint[] = allWeeks.map((w) => {
              const p = byWeek.get(w);
              return {
                key: w, label: weekLabel(w), value: p?.average_score ?? null,
                detail: p ? `${weekLabel(w)}: average ${p.average_score}/100 over ${p.answers} ${p.answers === 1 ? "answer" : "answers"}` : `${weekLabel(w)}: no answers`,
              };
            });
            return (
              <Card className="stack" key={t.evaluator}>
                <WeeklyBars title="Average score per week" points={points} max={100} unit="Average score (0-100)" emptyText="No scored answers in this range." />
                <p className="subtle">Scored by {t.evaluator}. {a.trends.length > 1 ? "Scores from different evaluators are shown separately and never combined." : "Scores measure rubric coverage, not correctness."}</p>
              </Card>
            );
          })}
          <Card className="stack">
            <h2 className="section-title">Question types answered</h2>
            {a.kinds.length === 0 ? <p className="subtle">None yet.</p> : (
              <table className="data-table">
                <thead><tr><th scope="col">Type</th><th scope="col">Answers</th></tr></thead>
                <tbody>{a.kinds.map((k) => <tr key={k.value}><td>{k.label}</td><td>{k.count}</td></tr>)}</tbody>
              </table>
            )}
          </Card>
          <Card className="stack">
            <details>
              <summary>How these numbers are defined</summary>
              <dl className="definitions">
                {Object.entries(a.definitions).map(([k, v]) => <div key={k}><dt>{cap(k.replace(/_/g, " "))}</dt><dd>{v}</dd></div>)}
              </dl>
            </details>
          </Card>
        </div>
      </div>
    </div>
  );
}
