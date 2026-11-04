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
import { LEVEL_UP_AFTER, LEVELS, nextLevel, RETRY_BELOW, upNext } from "./upNext";
import { MorePractice } from "./MorePractice";
import { StatTile } from "./StatTile";

/** The library lists at most this many questions per request; no level holds more. */
const LEVEL_PAGE = 100;

/** The dashboard for careers without coding problems: built only from that career's questions. */
export function CareerDashboard({ track, careerTitle }: { track: string; careerTitle?: string }) {
  const { user } = useAuth();
  const progress = useTrackProgress(track);
  const counts = useQuestionCounts(track, "");
  const level = progress.data ? nextLevel(progress.data.by_difficulty) : "easy";
  const questions = useQuestions(track, { difficulty: level, page: 1, page_size: LEVEL_PAGE });
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
  const next = upNext(questions.data?.items ?? [], counts.data?.[level]);
  const role = careerTitle ?? titleCase(track);
  const levelName = titleCase(level);
  const atLevel = p.by_difficulty[level] ?? 0;

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
      <MorePractice coding={false} />

      <section className="stat-row" aria-label="Summary">
        <StatTile icon="target" label="Questions answered" value={`${p.answered}`} detail={`of ${p.total_questions}, each counted once however many tries`}
          fraction={p.total_questions ? p.answered / p.total_questions : 0} />
        <StatTile icon="spark" label="Strong answers" value={`${p.strong}`} detail="Questions whose best score is 85 or more" />
        <StatTile icon="clock" label="Interviews completed" value={`${analytics.data?.interviews.completed ?? 0}`}
          detail={analytics.data && analytics.data.interviews.abandoned + analytics.data.interviews.expired > 0
            ? `${analytics.data.interviews.abandoned + analytics.data.interviews.expired} ended early or ran out of time` : "Mock interview rounds"} />
        <StatTile icon="chart" label="Skills practised" value={analytics.data ? `${covered} of ${analytics.data.skills.length}` : "…"}
          detail={trendText} />
      </section>

      {p.answered === 0 && (
        <div className="dashboard-onboarding"><span className="icon-tile"><Icon name="book" /></span><div><strong>Your dashboard fills in as you practice</strong><p className="subtle">Answer a question in your own words and you'll get a score, what you covered and what to add.</p></div><Link to={library} className="btn btn--secondary btn--md">Answer a question <Icon name="arrow" size={15} /></Link></div>
      )}

      <div className="dashboard__layout">
        <div className="dashboard__col">
          <Card className="stack">
            <div className="section-heading"><h2 className="section-title">Up next</h2><Link to={library}>All questions <span aria-hidden="true">→</span></Link></div>
            <p className="subtle up-next__why">
              Picked from your own answers by a fixed rule: questions whose best score is under {RETRY_BELOW} come back first,
              then {level} questions you haven't answered. {level === "hard" && atLevel >= LEVEL_UP_AFTER
                ? "You've answered at least 10 questions at every level, so this stays on hard."
                : `You're on ${levelName} (${atLevel} of ${LEVEL_UP_AFTER} answered there before it moves up a level).`}
            </p>
            {questions.isPending ? <LoadingState /> : questions.isError ? <ErrorState error={questions.error} onRetry={() => questions.refetch()} /> : (
              next.retry.length + next.fresh.length === 0
                ? <p className="subtle">{next.levelDone
                    ? `Every ${level} question has an answer with a best score of ${RETRY_BELOW} or more. Pick another level in the question library.`
                    : `Nothing to suggest from the ${level} questions listed here. The question library has the full list.`}</p>
                : (
                  <ul className="rec-list">
                    {[...next.retry, ...next.fresh].map((q) => (
                      <li key={q.id}>
                        <Link to={`/careers/${track}/questions/${q.id}`} className="rec">
                          <span className="row">
                            <strong>{q.title}</strong>
                            <DifficultyBadge difficulty={q.difficulty as Difficulty} />
                            <Badge>{q.best_score != null ? "Try again" : KIND_LABEL[q.kind] ?? titleCase(q.kind)}</Badge>
                          </span>
                          <span className="subtle">
                            {q.best_score != null ? `Your best score here is ${q.best_score}, under ${RETRY_BELOW}.` : q.prompt}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )
            )}
            {p.answered > 0 && (
              <Link to={`${library}?view=questions&status=attempted&sort=lowest_score`}>
                Review your answered questions, lowest score first <span aria-hidden="true">→</span>
              </Link>
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
