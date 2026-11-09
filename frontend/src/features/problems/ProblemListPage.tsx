import { useMemo } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { useProblemCounts, useProblems, useProgress, useRecommendations, useTopics } from "@/api/queries";
import type { Difficulty, Progress } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { DifficultyBadge, TopicTag } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useScrollMemory } from "@/hooks/useScrollMemory";
import { Icon } from "@/components/Icon";
import { Tabs } from "@/components/Tabs";
import { PracticeBar } from "@/features/careers/PracticeBar";
import { useBrowseCareer, withCareer } from "@/features/careers/practiceTrack";

/** Each tab starts with a short list; "View more" grows it. */
const FIRST_PAGE = 5;
const MORE_STEP = 10;
/** A hand-edited ?shown= can't ask for an unbounded page. */
const MAX_SHOWN = 200;
const DIFFICULTIES = [
  { id: "easy", label: "Easy" },
  { id: "medium", label: "Medium" },
  { id: "hard", label: "Hard" },
] as const satisfies readonly { id: Difficulty; label: string }[];

type ProblemStatus = Progress["problems"][number]["status"];
const STATUS_ICON: Record<ProblemStatus, { icon: string; label: string }> = {
  solved: { icon: "✓", label: "Solved" },
  attempted: { icon: "◐", label: "Attempted" },
  in_progress: { icon: "•", label: "In progress" },
  not_started: { icon: "", label: "Not started" },
};

const SEARCH_EXAMPLES = ["reverse words", "longest substring", "dp", "two pointers", "stack brackets"];

function isDifficulty(value: string | null): value is Difficulty {
  return value === "easy" || value === "medium" || value === "hard";
}

export function ProblemListPage() {
  const { isAuthenticated } = useAuth();
  const { keep } = useBrowseCareer();
  const [params, setParams] = useSearchParams();
  const raw = params.get("difficulty");
  const difficulty: Difficulty = isDifficulty(raw) ? raw : "easy";
  const topic = params.get("topic") ?? "";
  const search = params.get("q") ?? "";
  const q = useDebouncedValue(search.trim(), 300);
  // How many rows the open tab shows ("View more"), in the URL too, so coming back from a problem
  // (or reloading) shows the same rows. Any other change (tab, topic, search) starts again.
  const shownParam = Number(params.get("shown"));
  const visible = Number.isInteger(shownParam) && shownParam > FIRST_PAGE ? Math.min(shownParam, MAX_SHOWN) : FIRST_PAGE;
  const location = useLocation();

  // Keep the URL as the source of truth so filtered views are shareable and survive refresh.
  function update(next: Record<string, string>) {
    const merged = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) merged.set(k, v);
      else merged.delete(k);
    }
    merged.delete("page");
    if (!("shown" in next)) merged.delete("shown");
    setParams(merged, { replace: true });
  }

  const problems = useProblems({ difficulty, topic, q, page: 1, page_size: visible });
  useScrollMemory(Boolean(problems.data) && !problems.isPlaceholderData && !problems.isFetching);
  const counts = useProblemCounts({ topic, q });
  const topics = useTopics();
  const progress = useProgress(isAuthenticated);
  const statusBySlug = useMemo(
    () => new Map(progress.data?.problems.map((p) => [p.slug, p.status]) ?? []),
    [progress.data],
  );
  const hasFilters = Boolean(topic || q);
  const settling = problems.isFetching || q !== search.trim();
  const libraryTotal = counts.data ? counts.data.easy + counts.data.medium + counts.data.hard : null;
  const total = problems.data?.total ?? 0;
  const otherTabsWithMatches = counts.data
    ? DIFFICULTIES.filter((d) => d.id !== difficulty && counts.data[d.id] > 0)
    : [];

  return (
    <div className="page problems">
      <div className="page__header">
        <div>
          <p className="eyebrow">THE PRACTICE LIBRARY</p>
          <h1 className="page__title">Practice problems</h1>
          <p className="page__subtitle">
            {libraryTotal !== null && !hasFilters ? `${libraryTotal} problem${libraryTotal === 1 ? "" : "s"}` : "Curated Java interview problems"}
            {progress.data && ` · ${progress.data.solved} solved`}
          </p>
        </div>
        <div className="library-badge"><Icon name="code" size={18} /><span>Java, one problem at a time.</span></div>
      </div>

      <div className="problems__layout">
        <section aria-label="Problem list" className="stack">
          <PracticeBar view="coding" />
          <div className="filters filters--single" role="search">
            <label className="field filters__search">
              <span className="visually-hidden">Search problems</span>
              <Icon name="search" size={18} />
              <input className="input" type="search" value={search}
                placeholder="Search by keyword or what you want to practice, e.g. “reverse words”"
                onChange={(e) => update({ q: e.target.value })} />
            </label>
          </div>
          {!search && (
            <p className="search-examples subtle">
              Try:{" "}
              {SEARCH_EXAMPLES.map((example, i) => (
                <span key={example}>{i > 0 && " · "}<button type="button" className="link-button" onClick={() => update({ q: example })}>{example}</button></span>
              ))}
            </p>
          )}

          {topics.data && (
            <div className="chips" role="group" aria-label="Filter by topic">
              {topics.data.map((t) => (
                <button key={t.topic} type="button" className={`chip${topic === t.topic ? " chip--active" : ""}`}
                  aria-pressed={topic === t.topic} onClick={() => update({ topic: topic === t.topic ? "" : t.topic })}>
                  {t.topic.replace(/-/g, " ")} <span className="chip__count">{t.count}</span>
                </button>
              ))}
            </div>
          )}

          {hasFilters && (
            <div className="active-filters" role="status">
              <span>{settling ? "Searching…" : `${libraryTotal ?? 0} matching problem${libraryTotal === 1 ? "" : "s"} across all levels`}</span>
              <Button size="sm" variant="ghost" onClick={() => setParams(difficulty === "easy" ? {} : { difficulty }, { replace: true })}>Clear filters</Button>
            </div>
          )}

          <Tabs label="Difficulty" value={difficulty} onChange={(d) => update({ difficulty: d === "easy" ? "" : d })}
            listClassName="difficulty-tabs" panelClassName="difficulty-panel"
            tabs={DIFFICULTIES.map((d) => ({
              id: d.id,
              label: <>{d.label}{counts.data && <>{" "}<span className="difficulty-tabs__count">{counts.data[d.id]}</span></>}</>,
            }))}>
            {problems.isPending ? (
              <LoadingState label="Loading problems…" />
            ) : problems.isError ? (
              <ErrorState error={problems.error} onRetry={() => problems.refetch()} />
            ) : problems.data.items.length === 0 ? (
              <EmptyState title={hasFilters ? `No ${difficulty} problems match` : `No ${difficulty} problems yet`}
                action={otherTabsWithMatches.length > 0 ? (
                  <span className="row">{otherTabsWithMatches.map((d) => (
                    <Button key={d.id} size="sm" onClick={() => update({ difficulty: d.id === "easy" ? "" : d.id })}>
                      See {counts.data?.[d.id]} in {d.label}
                    </Button>
                  ))}</span>
                ) : hasFilters ? <Button onClick={() => setParams({}, { replace: true })}>Reset search</Button> : undefined}>
                {otherTabsWithMatches.length > 0 ? "Other levels have matches." : "Try a different search or topic."}
              </EmptyState>
            ) : (
              <>
                <ul className="problem-list" aria-busy={settling}>
                  {problems.data.items.map((p, index) => {
                    const status = statusBySlug.get(p.slug) ?? "not_started";
                    return (
                      <li key={p.slug}>
                        <Link to={`/problems/${p.slug}`} className="problem-row"
                          state={{ from: location.pathname + location.search, fromLabel: "Back to coding problems" }}>
                          <span className={`problem-row__status problem-row__status--${status}`}
                            title={STATUS_ICON[status].label} aria-label={STATUS_ICON[status].label}>
                            {STATUS_ICON[status].icon}
                          </span>
                          <span className="problem-row__main">
                            <span className="problem-row__title"><span className="problem-row__number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>{p.title}</span>
                            <span className="problem-row__summary">{p.summary}</span>
                          </span>
                          <span className="problem-row__meta">
                            {p.topics.slice(0, 2).map((t) => <TopicTag key={t} topic={t} />)}
                            <DifficultyBadge difficulty={p.difficulty} />
                            <Icon className="problem-row__arrow" name="arrow" size={16} />
                          </span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
                <div className="view-more">
                  <span className="subtle">Showing {problems.data.items.length} of {total}</span>
                  {problems.data.items.length < total && (
                    <Button size="sm" loading={problems.isFetching}
                      onClick={() => update({ shown: String(visible + MORE_STEP) })}>
                      View more
                    </Button>
                  )}
                </div>
              </>
            )}
          </Tabs>
        </section>

        <aside className="library-aside">
          {isAuthenticated && progress.data && <Card className="library-progress stack"><div className="library-progress__head"><h2 className="section-title">Your progress</h2><p className="library-progress__count">{progress.data.solved}<span> / {progress.data.total_problems} solved</span></p></div><progress aria-label="Problem completion" value={progress.data.solved} max={Math.max(progress.data.total_problems, 1)} /><Link to="/analytics">Explore your progress <Icon name="arrow" size={14} /></Link></Card>}
          {isAuthenticated && <RecommendationsAside />}
          <Card className="library-interview stack"><h2><Icon name="clock" size={17} />Make it an interview</h2><p className="subtle">Practice your approach out loud, work against the clock, and learn from your feedback.</p><Link to={withCareer("/interviews", keep)}>Try a mock interview <Icon name="arrow" size={14} /></Link></Card>
        </aside>
      </div>
    </div>
  );
}

function RecommendationsAside() {
  const recs = useRecommendations(3);
  if (recs.isPending || recs.isError || recs.data.length === 0) return null;
  return (
    <section aria-label="Recommended for you">
      <Card className="stack">
        <h2 className="section-title">Recommended for you</h2>
        {recs.data.map((r) => (
          <Link key={r.slug} to={`/problems/${r.slug}`} className="rec">
            <span className="row"><strong>{r.title}</strong><DifficultyBadge difficulty={r.difficulty} /></span>
            <span className="subtle">{r.reason}</span>
          </Link>
        ))}
      </Card>
    </section>
  );
}
