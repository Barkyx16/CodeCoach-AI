import { useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import type { ExploreFilters } from "@/api/endpoints";
import { useExplore, useToggleBookmark, useTrackProgress } from "@/api/queries";
import type { Difficulty, ExploreResult, ExploreSort, ItemStatus, MyExploreResult } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Badge, DifficultyBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Icon } from "@/components/Icon";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { Tabs } from "@/components/Tabs";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useScrollMemory } from "@/hooks/useScrollMemory";
import { describeError } from "@/lib/errors";

import { KIND_LABEL } from "./kinds";
import { PracticeBar } from "./PracticeBar";
import { usePracticeTrack } from "./practiceTrack";

const FIRST_PAGE = 5;
const MORE_STEP = 10;
const MAX_PAGE = 100; // the API's page size limit; no difficulty level has more questions than this
const LEVELS = [
  { id: "easy", label: "Easy" },
  { id: "medium", label: "Medium" },
  { id: "hard", label: "Hard" },
] as const satisfies readonly { id: Difficulty; label: string }[];
const EXAMPLES = ["tell me about a time", "under pressure", "mistake", "disagreement", "first 30 days"];
const STATUS_LABEL = { unattempted: "Not answered yet", attempted: "Answered", bookmarked: "Bookmarked" } as const;
type Status = keyof typeof STATUS_LABEL;
const SORT_LABEL: Record<ExploreSort, string> = {
  relevance: "Best match",
  library: "Library order",
  last_practiced: "Recently practiced",
  lowest_score: "Lowest score first",
};

function isLevel(v: string | null): v is Difficulty {
  return v === "easy" || v === "medium" || v === "hard";
}

function isStatus(v: string | null): v is Status {
  return v === "unattempted" || v === "attempted" || v === "bookmarked";
}

/** From answers long enough to score only (backend app/careers/eligibility.py). */
function scoreLabel(st: ItemStatus | undefined): string {
  if (!st || !st.score_status) return "Not answered";
  if (st.best_scored != null) return `Best score ${st.best_scored}`;
  return st.score_status === "too_short" ? "Answered, too short to score" : "Answered (how it was graded wasn't recorded)";
}

/**
 * Interview questions for one career: search, Easy/Medium/Hard tabs, format/skill/status filters with
 * counts, sorts, removable filter chips, bookmarks, and "View more". Everything that shapes the
 * result set lives in the URL, so Back, Forward, reload and shared links show the same list.
 */
export function QuestionLibrary() {
  const { isAuthenticated } = useAuth();
  const { track, career } = usePracticeTrack();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const raw = params.get("difficulty");
  const difficulty: Difficulty = isLevel(raw) ? raw : "easy";
  const search = params.get("q") ?? "";
  const q = useDebouncedValue(search.trim(), 300);
  const kind = params.get("kind") ?? "";
  const skill = params.get("skill") ?? "";
  const rawStatus = params.get("status");
  const status = isAuthenticated && isStatus(rawStatus) ? rawStatus : undefined;
  const sortParam = params.get("sort") as ExploreSort | null;
  const visible = Math.min(Math.max(Number(params.get("shown")) || FIRST_PAGE, FIRST_PAGE), MAX_PAGE);

  /** Discrete choices push a history entry (Back undoes them); typing and "View more" replace. */
  function update(next: Record<string, string>, { replace = false } = {}) {
    const merged = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) merged.set(k, v);
      else merged.delete(k);
    }
    if (!("shown" in next)) merged.delete("shown");
    setParams(merged, { replace });
  }

  const filters: ExploreFilters = {
    q: q || undefined, difficulty, kind: kind || undefined, skill: skill || undefined, status,
    sort: sortParam ?? undefined, page: 1, page_size: visible,
  };
  const explore = useExplore(track, filters, isAuthenticated);
  const progress = useTrackProgress(track, isAuthenticated);
  const bookmark = useToggleBookmark();
  const [bookmarkError, setBookmarkError] = useState<{ title: string; on: boolean; id: string; error: unknown } | null>(null);
  const data = explore.data as (ExploreResult & Partial<Pick<MyExploreResult, "status">>) | undefined;
  useScrollMemory(Boolean(data) && !explore.isPlaceholderData);

  const settling = explore.isFetching || q !== search.trim();
  const total = data?.total ?? 0;
  const counts = Object.fromEntries((data?.facets.difficulty ?? []).map((f) => [f.value, f.count])) as Partial<Record<Difficulty, number>>;
  const otherLevels = data ? LEVELS.filter((l) => l.id !== difficulty && (counts[l.id] ?? 0) > 0) : [];
  const title = career ? `${career.title} interview questions` : "Interview questions";
  const sort = sortParam && data?.sorts.includes(sortParam) ? sortParam : q ? "relevance" : "library";
  const chips = [
    q && { key: "q", label: `Search: “${q}”` },
    kind && { key: "kind", label: `Format: ${KIND_LABEL[kind] ?? kind}` },
    skill && { key: "skill", label: `Skill: ${skill}` },
    status && { key: "status", label: STATUS_LABEL[status] },
  ].filter(Boolean) as { key: string; label: string }[];
  const back = { from: `${location.pathname}${location.search}`, fromLabel: "Back to results" };

  function toggleBookmark(id: string, itemTitle: string, on: boolean) {
    setBookmarkError(null);
    bookmark.mutate({ ref: { item_type: "question", track, ref_id: id }, on }, {
      onError: (error) => setBookmarkError({ id, title: itemTitle, on, error }),
    });
  }

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
        {isAuthenticated && <Link className="btn btn--secondary btn--md" to="/saved"><Icon name="bookmark" size={16} />Saved</Link>}
      </div>

      <div className="problems__layout">
        <section aria-label="Question list" className="stack">
          <PracticeBar view="questions" />
          <div className="filters filters--single" role="search">
            <label className="field filters__search">
              <span className="visually-hidden">Search questions</span>
              <Icon name="search" size={18} />
              <input className="input" type="search" value={search}
                placeholder="Search by keyword, skill or topic, e.g. “triage” or “mistake”"
                onChange={(e) => update({ q: e.target.value }, { replace: true })} />
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

          <div className="explore-filters" role="group" aria-label="Filters">
            <label className="explore-filter">
              <span>Format</span>
              <select className="input" value={kind} onChange={(e) => update({ kind: e.target.value })}>
                <option value="">Any format</option>
                {data?.facets.kind.map((f) => (
                  <option key={f.value} value={f.value} disabled={f.count === 0 && f.value !== kind}>{f.label} ({f.count})</option>
                ))}
              </select>
            </label>
            <label className="explore-filter">
              <span>Skill</span>
              <select className="input" value={skill} onChange={(e) => update({ skill: e.target.value })}>
                <option value="">Any skill</option>
                {data?.facets.skill.map((f) => (
                  <option key={f.value} value={f.value} disabled={f.count === 0 && f.value !== skill}>{f.label} ({f.count})</option>
                ))}
              </select>
            </label>
            {isAuthenticated && (
              <label className="explore-filter">
                <span>Your practice</span>
                <select className="input" value={status ?? ""} onChange={(e) => update({ status: e.target.value })}>
                  <option value="">All questions</option>
                  {(Object.keys(STATUS_LABEL) as Status[]).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
                </select>
              </label>
            )}
            <label className="explore-filter">
              <span>Sort</span>
              <select className="input" value={sort} onChange={(e) => {
                const v = e.target.value as ExploreSort;
                update({ sort: v === (q ? "relevance" : "library") ? "" : v });
              }}>
                {(data?.sorts ?? [sort]).map((s) => <option key={s} value={s}>{SORT_LABEL[s]}</option>)}
              </select>
            </label>
          </div>
          <p className="subtle explore-note">
            {isAuthenticated ? "" : "Sign in to filter by what you've answered or bookmarked. "}
            Time estimates aren't shown: the question bank doesn't time these questions.
          </p>

          {chips.length > 0 && (
            <div className="filter-chips" aria-label="Active filters" role="group">
              {chips.map((c) => (
                <button key={c.key} type="button" className="filter-chip" aria-label={`Remove ${c.label}`}
                  onClick={() => update({ [c.key]: "" })}>
                  {c.label}<span aria-hidden="true"> ✕</span>
                </button>
              ))}
              {chips.length > 1 && (
                <Button size="sm" variant="ghost" onClick={() => update({ q: "", kind: "", skill: "", status: "" })}>Clear all</Button>
              )}
            </div>
          )}
          {(chips.length > 0 || sortParam) && data && (
            <p className="active-filters" role="status">
              {settling ? "Searching…" : [`${total} ${total === 1 ? "question" : "questions"}`, ...data.explanation, `Sorted by ${SORT_LABEL[sort].toLowerCase()}`].join(" · ")}
            </p>
          )}

          <Tabs label="Difficulty" value={difficulty} onChange={(d) => update({ difficulty: d === "easy" ? "" : d })}
            listClassName="difficulty-tabs" panelClassName="difficulty-panel"
            tabs={LEVELS.map((l) => ({
              id: l.id,
              label: <>{l.label}{data && <>{" "}<span className="difficulty-tabs__count">{counts[l.id] ?? 0}</span></>}</>,
            }))}>
            {bookmarkError && (
              <div className="banner banner--warning stack-sm" role="alert">
                <p>Couldn't {bookmarkError.on ? "bookmark" : "remove the bookmark from"} “{bookmarkError.title}”. Nothing was changed.</p>
                <p className="subtle">{describeError(bookmarkError.error).message}</p>
                <span className="row">
                  <Button size="sm" onClick={() => toggleBookmark(bookmarkError.id, bookmarkError.title, bookmarkError.on)}>Try again</Button>
                  <Button size="sm" variant="ghost" onClick={() => setBookmarkError(null)}>Dismiss</Button>
                </span>
              </div>
            )}
            {explore.isPending ? (
              <LoadingState label="Loading questions…" />
            ) : explore.isError ? (
              <ErrorState error={explore.error} onRetry={() => explore.refetch()} />
            ) : data!.items.length === 0 ? (
              <EmptyState title={`No ${difficulty} questions match`}
                action={
                  <span className="row">
                    {otherLevels.map((l) => (
                      <Button key={l.id} size="sm" onClick={() => update({ difficulty: l.id === "easy" ? "" : l.id })}>
                        See {counts[l.id]} in {l.label}
                      </Button>
                    ))}
                    {chips.length > 0 && <Button size="sm" variant="ghost" onClick={() => update({ q: "", kind: "", skill: "", status: "" })}>Clear filters</Button>}
                  </span>
                }>
                {otherLevels.length > 0 ? "Other levels have matches. " : ""}
                {data!.suggestions.join(" ")}
              </EmptyState>
            ) : (
              <>
                <ul className="problem-list" aria-busy={settling}>
                  {data!.items.map((item, index) => {
                    const st = data!.status?.[item.id];
                    const label = scoreLabel(st);
                    const answered = !!st?.score_status;
                    const best = st?.best_scored;
                    return (
                      <li key={item.id} className="explore-row">
                        <Link to={`/careers/${track}/questions/${item.id}`} state={back} className="problem-row">
                          <span className={`problem-row__status problem-row__status--${!answered ? "not_started" : best != null && best >= 85 ? "solved" : "attempted"}`}
                            title={label} aria-label={label}>
                            {!answered ? "" : best != null && best >= 85 ? "✓" : "◐"}
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
                        {isAuthenticated && (
                          <button type="button" className="bookmark-toggle" aria-pressed={Boolean(st?.bookmarked)}
                            aria-label={`Bookmark “${item.title}”`} title={st?.bookmarked ? "Bookmarked" : "Bookmark"}
                            onClick={() => toggleBookmark(item.id, item.title, !st?.bookmarked)}>
                            <Icon name="bookmark" size={18} />
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ul>
                <div className="view-more">
                  <span className="subtle">Showing {data!.items.length} of {total}</span>
                  {data!.items.length < total && visible < MAX_PAGE && (
                    <Button size="sm" loading={explore.isFetching}
                      onClick={() => update({ shown: String(Math.min(visible + MORE_STEP, MAX_PAGE)) }, { replace: true })}>
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
