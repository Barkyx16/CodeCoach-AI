import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useProblems, useProgress, useRecommendations, useTopics } from "@/api/queries";
import type { Difficulty, Progress } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { DifficultyBadge, TopicTag } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { Icon } from "@/components/Icon";

const PAGE_SIZE = 20;
const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard"];

type ProblemStatus = Progress["problems"][number]["status"];
const STATUS_ICON: Record<ProblemStatus, { icon: string; label: string }> = {
  solved: { icon: "✓", label: "Solved" },
  attempted: { icon: "◐", label: "Attempted" },
  in_progress: { icon: "•", label: "In progress" },
  not_started: { icon: "", label: "Not started" },
};

export function ProblemListPage() {
  const { isAuthenticated } = useAuth();
  const [params, setParams] = useSearchParams();
  const difficulty = (params.get("difficulty") ?? "") as Difficulty | "";
  const topic = params.get("topic") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? 1) || 1);
  const search = params.get("q") ?? "";
  const q = useDebouncedValue(search.trim(), 300);

  // Keep the URL as the source of truth so filtered views are shareable and survive refresh.
  function update(next: Record<string, string>) {
    const merged = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) merged.set(k, v);
      else merged.delete(k);
    }
    if (!("page" in next)) merged.delete("page");
    setParams(merged, { replace: true });
  }

  const filters = { difficulty, topic, q, page, page_size: PAGE_SIZE };
  const problems = useProblems(filters);
  const topics = useTopics();
  const progress = useProgress(isAuthenticated);
  const statusBySlug = useMemo(
    () => new Map(progress.data?.problems.map((p) => [p.slug, p.status]) ?? []),
    [progress.data],
  );
  const hasFilters = Boolean(difficulty || topic || q);
  const totalPages = problems.data ? Math.max(1, Math.ceil(problems.data.total / PAGE_SIZE)) : 1;

  return (
    <div className="page problems">
      <div className="page__header">
        <div>
          <p className="eyebrow">THE PRACTICE LIBRARY</p>
          <h1 className="page__title">Practice problems</h1>
          <p className="page__subtitle">
            {problems.data ? `${problems.data.total} problem${problems.data.total === 1 ? "" : "s"}` : "Curated Java interview problems"}
            {progress.data && ` · ${progress.data.solved} solved`}
          </p>
        </div>
        <div className="library-badge"><Icon name="code" size={18} /><span>Java, one problem at a time.</span></div>
      </div>

      <div className="problems__layout">
        <section aria-label="Problem list" className="stack">
          <div className="library-intro"><h2>Find your next challenge.</h2><p>Work on a weak spot, explore a new topic, or finish what you started.</p></div>
          <div className="filters" role="search">
            <label className="field filters__search">
              <span className="visually-hidden">Search problems</span>
              <Icon name="search" size={18} />
              <input className="input" type="search" placeholder="Search by title or description…" value={search}
                onChange={(e) => update({ q: e.target.value })} />
            </label>
            <label className="field">
              <span className="visually-hidden">Difficulty</span>
              <select className="select" value={difficulty} onChange={(e) => update({ difficulty: e.target.value })}>
                <option value="">All difficulties</option>
                {DIFFICULTIES.map((d) => <option key={d} value={d}>{d[0]?.toUpperCase() + d.slice(1)}</option>)}
              </select>
            </label>
          </div>

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

          {hasFilters && <div className="active-filters"><span>{problems.isFetching || q !== search.trim() ? "Updating challenges…" : `${problems.data?.total ?? 0} matching challenges`}</span><Button size="sm" variant="ghost" onClick={() => setParams({}, { replace: true })}>Clear filters</Button></div>}

          {problems.isPending ? (
            <LoadingState label="Loading problems…" />
          ) : problems.isError ? (
            <ErrorState error={problems.error} onRetry={() => problems.refetch()} />
          ) : problems.data.items.length === 0 ? (
            <EmptyState title="No problems match"
              action={hasFilters ? <Button onClick={() => setParams({}, { replace: true })}>Reset search</Button> : undefined}>
              Try a different search or topic.
            </EmptyState>
          ) : (
            <ul className="problem-list" aria-busy={problems.isFetching || q !== search.trim()}>
              {problems.data.items.map((p, index) => {
                const status = statusBySlug.get(p.slug) ?? "not_started";
                return (
                  <li key={p.slug}>
                    <Link to={`/problems/${p.slug}`} className="problem-row">
                      <span className={`problem-row__status problem-row__status--${status}`}
                        title={STATUS_ICON[status].label} aria-label={STATUS_ICON[status].label}>
                        {STATUS_ICON[status].icon}
                      </span>
                      <span className="problem-row__main">
                        <span className="problem-row__title"><span className="problem-row__number" aria-hidden="true">{String((page - 1) * PAGE_SIZE + index + 1).padStart(2, "0")}</span>{p.title}</span>
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
          )}

          {problems.data && totalPages > 1 && (
            <nav className="pagination" aria-label="Pagination">
              <Button size="sm" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>Previous</Button>
              <span className="subtle">Page {page} of {totalPages}</span>
              <Button size="sm" disabled={page >= totalPages} onClick={() => update({ page: String(page + 1) })}>Next</Button>
            </nav>
          )}
        </section>

        <aside className="library-aside">
          {isAuthenticated && progress.data && <Card className="library-progress stack"><div className="section-heading"><span className="icon-tile"><Icon name="target" /></span><span className="badge">Your progress</span></div><p className="library-progress__count">{progress.data.solved}<span> / {progress.data.total_problems}</span></p><p className="subtle">problems solved</p><progress aria-label="Problem completion" value={progress.data.solved} max={Math.max(progress.data.total_problems, 1)} /><Link to="/analytics">Explore your progress <Icon name="arrow" size={14} /></Link></Card>}
          {isAuthenticated && <RecommendationsAside />}
          <Card className="library-interview stack"><span className="icon-tile"><Icon name="clock" /></span><h2>Make it an interview.</h2><p className="subtle">Practice your approach out loud, work against the clock, and learn from your feedback.</p><Link to="/interviews">Try a mock interview <Icon name="arrow" size={14} /></Link></Card>
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
