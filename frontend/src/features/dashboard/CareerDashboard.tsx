import { Link } from "react-router-dom";

import { useCareerAnalytics, useQuestionCounts, useQuestions, useTrackProgress } from "@/api/queries";
import type { Difficulty } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Badge, DifficultyBadge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { Icon } from "@/components/Icon";
import { ErrorState, LoadingState } from "@/components/States";
import { titleCase } from "@/lib/format";
import { KIND_LABEL } from "@/features/careers/kinds";

import { ProgressBars } from "./ProgressBars";
import { TodayCard } from "@/features/plan/TodayCard";
import { OnboardingBanner } from "@/features/onboarding/OnboardingBanner";

import { ContinueCard } from "./ContinueCard";
import { StatTile } from "./StatTile";

const LEVELS: Difficulty[] = ["easy", "medium", "hard"];
/** Answers at a level before "Up next" moves on to the next one. */
const LEVEL_UP_AFTER = 10;

/** The level to practice next: the first with fewer than LEVEL_UP_AFTER answers, else hard. */
function nextLevel(answered: Record<string, number>): Difficulty {
  return LEVELS.find((l) => (answered[l] ?? 0) < LEVEL_UP_AFTER) ?? "hard";
}

/** The dashboard for careers without coding problems: built only from that career's questions. */
export function CareerDashboard({ track, careerTitle }: { track: string; careerTitle?: string }) {
  const { user } = useAuth();
  const progress = useTrackProgress(track);
  const counts = useQuestionCounts(track, "");
  const level = progress.data ? nextLevel(progress.data.by_difficulty) : "easy";
  const questions = useQuestions(track, { difficulty: level, page: 1, page_size: 60 });
  const analytics = useCareerAnalytics(track, undefined);
  const covered = analytics.data?.skills.filter((s) => s.questions_answered > 0).length ?? 0;
  // A trend only within one evaluator, and only once there are two weeks to compare.
  const series = analytics.data?.trends.length === 1 ? analytics.data.trends[0]!.points : [];
  const trendText = series.length >= 2
    ? `Weekly average ${series.at(-2)!.average_score} → ${series.at(-1)!.average_score}`
    : "Practising level: " + titleCase(level);

  if (progress.isPending) return <LoadingState label="Loading your progress…" />;
  if (progress.isError) return <div className="page"><ErrorState error={progress.error} onRetry={() => progress.refetch()} /></div>;
  const p = progress.data;
  const library = `/problems`;
  const items = questions.data?.items ?? [];
  const upNext = items.filter((q) => q.best_score == null).slice(0, 3);
  const retry = items.filter((q) => q.best_score != null && q.best_score < 70).slice(0, 2);
  const role = careerTitle ?? titleCase(track);

  return (
    <div className="page dashboard">
      <div className="page__header">
        <div>
          <p className="eyebrow">{role.toUpperCase()} INTERVIEW PRACTICE</p>
          <h1 className="page__title">{user?.display_name ? `${user.display_name}'s progress` : "Your progress"}</h1>
          <p className="page__subtitle">Questions written for {role} interviews.</p>
        </div>
        <div className="row dashboard__actions">
          <Link to="/interviews" className="btn btn--secondary btn--md">Mock interview</Link>
          <Link to={library} className="btn btn--primary btn--md">Practice questions <span aria-hidden="true">→</span></Link>
        </div>
      </div>

      <OnboardingBanner />
      <TodayCard />
      <ContinueCard />

      <section className="stat-row" aria-label="Summary">
        <StatTile icon="target" label="Answered" value={`${p.answered}`} detail={`of ${p.total_questions} questions`}
          fraction={p.total_questions ? p.answered / p.total_questions : 0} />
        <StatTile icon="spark" label="Strong answers" value={`${p.strong}`} detail="Best score of 85 or more" />
        <StatTile icon="clock" label="Interviews completed" value={`${analytics.data?.interviews.completed ?? 0}`}
          detail={analytics.data && analytics.data.interviews.abandoned + analytics.data.interviews.expired > 0
            ? `${analytics.data.interviews.abandoned + analytics.data.interviews.expired} ended early or ran out of time` : "Mock interview rounds"} />
        <StatTile icon="chart" label="Skills covered" value={analytics.data ? `${covered} of ${analytics.data.skills.length}` : "…"}
          detail={trendText} />
      </section>

      {p.answered === 0 && (
        <div className="dashboard-onboarding"><span className="icon-tile"><Icon name="book" /></span><div><strong>Your dashboard fills in as you practice</strong><p className="subtle">Answer a question in your own words and you'll get a score, what you covered and what to add.</p></div><Link to={library} className="btn btn--secondary btn--md">Answer a question <Icon name="arrow" size={15} /></Link></div>
      )}

      <div className="dashboard__layout">
        <div className="dashboard__col">
          <Card className="stack">
            <div className="section-heading"><h2 className="section-title">Up next</h2><Link to={library}>All questions <span aria-hidden="true">→</span></Link></div>
            {questions.isPending ? <LoadingState /> : questions.isError ? <ErrorState error={questions.error} /> : (
              upNext.length + retry.length === 0
                ? <p className="subtle">You've answered every {level} question. Try another level from the question library.</p>
                : (
                  <ul className="rec-list">
                    {[...retry, ...upNext].map((q) => (
                      <li key={q.id}>
                        <Link to={`/careers/${track}/questions/${q.id}`} className="rec">
                          <span className="row">
                            <strong>{q.title}</strong>
                            <DifficultyBadge difficulty={q.difficulty as Difficulty} />
                            <Badge>{q.best_score != null ? "Try again" : KIND_LABEL[q.kind] ?? titleCase(q.kind)}</Badge>
                          </span>
                          <span className="subtle">
                            {q.best_score != null ? `Your best score is ${q.best_score}. Another try can lift it.` : q.prompt}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )
            )}
          </Card>
        </div>

        <div className="dashboard__col">
          <Card className="stack">
            <h2 className="section-title">Answered by difficulty</h2>
            <ProgressBars showAttempted={false} unit="answered"
              rows={LEVELS.map((l) => ({ key: l, label: titleCase(l), total: counts.data?.[l] ?? 0, solved: p.by_difficulty[l] ?? 0 }))} />
          </Card>
        </div>
      </div>
    </div>
  );
}
