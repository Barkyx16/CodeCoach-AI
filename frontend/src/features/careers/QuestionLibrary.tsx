import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useQuestionCounts, useQuestions, useTrackProgress } from "@/api/queries";
import type { Difficulty } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Badge, DifficultyBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Icon } from "@/components/Icon";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { Tabs } from "@/components/Tabs";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

import { KIND_LABEL } from "./kinds";
import { PracticeBar } from "./PracticeBar";
import { usePracticeTrack } from "./practiceTrack";

const FIRST_PAGE = 5;
const MORE_STEP = 10;
const LEVELS = [
  { id: "easy", label: "Easy" },
  { id: "medium", label: "Medium" },
  { id: "hard", label: "Hard" },
] as const satisfies readonly { id: Difficulty; label: string }[];
const EXAMPLES = ["tell me about a time", "under pressure", "mistake", "disagreement", "first 30 days"];

function isLevel(v: string | null): v is Difficulty {
  return v === "easy" || v === "medium" || v === "hard";
}

/** Interview questions for one career: Easy / Medium / Hard tabs, keyword search, 5 then "View more". */
export function QuestionLibrary() {
  const { isAuthenticated } = useAuth();
  const { track, career } = usePracticeTrack();
  const [params, setParams] = useSearchParams();
  const raw = params.get("difficulty");
  const difficulty: Difficulty = isLevel(raw) ? raw : "easy";
  const search = params.get("q") ?? "";
  const q = useDebouncedValue(search.trim(), 300);
  const [shown, setShown] = useState({ key: "", count: FIRST_PAGE });
  const viewKey = `${track}|${difficulty}|${q}`;
  const visible = shown.key === viewKey ? shown.count : FIRST_PAGE;

  function update(next: Record<string, string>) {
    const merged = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) merged.set(k, v);
      else merged.delete(k);
    }
    setParams(merged, { replace: true });
  }

  const questions = useQuestions(track, { difficulty, q, page: 1, page_size: visible });
  const counts = useQuestionCounts(track, q);
  const progress = useTrackProgress(track, isAuthenticated);
  const settling = questions.isFetching || q !== search.trim();
  const total = questions.data?.total ?? 0;
  const otherLevels = counts.data ? LEVELS.filter((l) => l.id !== difficulty && counts.data[l.id] > 0) : [];
  const title = career ? `${career.title} interview questions` : "Interview questions";

  return (
    <div className="page problems questions">
      <div className="page__header">
        <div>
          <p className="eyebrow">INTERVIEW PRACTICE</p>
          <h1 className="page__title">{title}</h1>
          <p className="page__subtitle">
            {career ? `${career.question_count} questions written for this job` : "Questions written for your job"}
            {progress.data && ` · ${progress.data.answered} answered`}
          </p>
        </div>
      </div>

      <div className="problems__layout">
        <section aria-label="Question list" className="stack">
          <PracticeBar view="questions" />
          <div className="filters filters--single" role="search">
            <label className="field filters__search">
              <span className="visually-hidden">Search questions</span>
              <Icon name="search" size={18} />
              <input className="input" type="search" value={search}
                placeholder="Search by keyword, e.g. “difficult customer” or “mistake”"
                onChange={(e) => update({ q: e.target.value })} />
            </label>
          </div>
          {!search && (
            <p className="search-examples subtle">
              Try:{" "}
              {EXAMPLES.map((example, i) => (
                <span key={example}>{i > 0 && " · "}<button type="button" className="link-button" onClick={() => update({ q: example })}>{example}</button></span>
              ))}
            </p>
          )}
          {q && (
            <div className="active-filters" role="status">
              <span>{settling ? "Searching…" : `${counts.data ? counts.data.easy + counts.data.medium + counts.data.hard : 0} matching questions across all levels`}</span>
              <Button size="sm" variant="ghost" onClick={() => update({ q: "" })}>Clear search</Button>
            </div>
          )}

          <Tabs label="Difficulty" value={difficulty} onChange={(d) => update({ difficulty: d === "easy" ? "" : d })}
            listClassName="difficulty-tabs" panelClassName="difficulty-panel"
            tabs={LEVELS.map((l) => ({
              id: l.id,
              label: <>{l.label}{counts.data && <>{" "}<span className="difficulty-tabs__count">{counts.data[l.id]}</span></>}</>,
            }))}>
            {questions.isPending ? (
              <LoadingState label="Loading questions…" />
            ) : questions.isError ? (
              <ErrorState error={questions.error} onRetry={() => questions.refetch()} />
            ) : questions.data.items.length === 0 ? (
              <EmptyState title={`No ${difficulty} questions match`}
                action={otherLevels.length > 0 ? (
                  <span className="row">{otherLevels.map((l) => (
                    <Button key={l.id} size="sm" onClick={() => update({ difficulty: l.id === "easy" ? "" : l.id })}>
                      See {counts.data?.[l.id]} in {l.label}
                    </Button>
                  ))}</span>
                ) : <Button onClick={() => update({ q: "" })}>Clear search</Button>}>
                {otherLevels.length > 0 ? "Other levels have matches." : "Try different words."}
              </EmptyState>
            ) : (
              <>
                <ul className="problem-list" aria-busy={settling}>
                  {questions.data.items.map((item, index) => (
                    <li key={item.id}>
                      <Link to={`/careers/${track}/questions/${item.id}`} className="problem-row">
                        <span className={`problem-row__status problem-row__status--${item.best_score === null || item.best_score === undefined ? "not_started" : item.best_score >= 85 ? "solved" : "attempted"}`}
                          title={item.best_score === null || item.best_score === undefined ? "Not answered" : `Best score ${item.best_score}`}
                          aria-label={item.best_score === null || item.best_score === undefined ? "Not answered" : `Best score ${item.best_score}`}>
                          {item.best_score === null || item.best_score === undefined ? "" : item.best_score >= 85 ? "✓" : "◐"}
                        </span>
                        <span className="problem-row__main">
                          <span className="problem-row__title"><span className="problem-row__number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>{item.title}</span>
                          <span className="problem-row__summary">{item.prompt}</span>
                        </span>
                        <span className="problem-row__meta">
                          <span className="topic-tag">{KIND_LABEL[item.kind] ?? item.kind}</span>
                          <DifficultyBadge difficulty={item.difficulty as Difficulty} />
                          <Icon className="problem-row__arrow" name="arrow" size={16} />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
                <div className="view-more">
                  <span className="subtle">Showing {questions.data.items.length} of {total}</span>
                  {questions.data.items.length < total && (
                    <Button size="sm" loading={questions.isFetching}
                      onClick={() => setShown({ key: viewKey, count: visible + MORE_STEP })}>
                      View more
                    </Button>
                  )}
                </div>
              </>
            )}
          </Tabs>
        </section>

        <aside className="library-aside">
          {isAuthenticated && progress.data && (
            <Card className="library-progress stack">
              <div className="library-progress__head">
                <h2 className="section-title">Your progress</h2>
                <p className="library-progress__count">{progress.data.answered}<span> / {progress.data.total_questions} answered</span></p>
              </div>
              <progress aria-label="Questions answered" value={progress.data.answered} max={Math.max(progress.data.total_questions, 1)} />
              <p className="subtle">{progress.data.strong} strong answers (85+)</p>
            </Card>
          )}
          <Card className="library-interview stack">
            <h2><Icon name="spark" size={17} />How feedback works</h2>
            <p className="subtle">Write your answer as you'd say it. You'll see what you covered, what's missing and what a strong answer includes.</p>
            <ul className="mini-list subtle">
              <li>Behavioral: use Situation, Task, Action, Result.</li>
              <li>Scenarios: assess, prioritize, act, communicate, follow up.</li>
            </ul>
            {!isAuthenticated && <Badge tone="info">Sign in or try as a guest to get feedback</Badge>}
          </Card>
        </aside>
      </div>
    </div>
  );
}
