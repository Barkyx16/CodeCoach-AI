import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { useActivity, useActivityFacets } from "@/api/queries";
import type { ActivityItem } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { formatDateTime, timeAgo } from "@/lib/format";

import { PAGE_SIZE, filtersFromParams, hasFilters } from "./historyState";

const TYPE_TONE: Record<ActivityItem["type"], string> = {
  problem_opened: "neutral",
  code_submission: "info",
  coaching: "info",
  written_answer: "success",
  interview: "warning",
};
const TYPE_SHORT: Record<ActivityItem["type"], string> = {
  problem_opened: "Opened",
  code_submission: "Submission",
  coaching: "Coaching",
  written_answer: "Answer",
  interview: "Interview",
};
// Older links used ?tab=…; keep them working.
const LEGACY_TABS: Record<string, string> = { submissions: "code_submission", ai: "coaching", interviews: "interview" };

/** Everything practised, across careers, with filters in the URL (so Back restores them). */
export function HistoryPage() {
  const [params, setParams] = useSearchParams();
  const legacy = params.get("tab");
  useEffect(() => {
    if (legacy && LEGACY_TABS[legacy]) setParams({ type: LEGACY_TABS[legacy] }, { replace: true });
  }, [legacy, setParams]);
  const filters = filtersFromParams(params);
  const [search, setSearch] = useState(filters.q ?? "");
  const q = useDebouncedValue(search.trim(), 300);
  const facets = useActivityFacets(filters.career);
  const activity = useActivity({ ...filters, page_size: PAGE_SIZE });

  // The filters as last set by this page: two changes in quick succession (a career, then a type)
  // must build on each other, not each on the URL of the last render (the second used to drop
  // the first). Synced back whenever the URL changes from elsewhere (Back, a link).
  const latest = useRef(params);
  useEffect(() => {
    latest.current = params;
  }, [params]);

  function update(patch: Record<string, string | undefined>, resetPage = true) {
    const next = new URLSearchParams(latest.current);
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (resetPage) next.delete("page");
    if ("career" in patch) next.delete("skill"); // skills belong to one career
    latest.current = next;
    setParams(next, { replace: !("page" in patch) });
  }
  useEffect(() => {
    if ((filters.q ?? "") !== q) update({ q: q || undefined });
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const total = activity.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const f = facets.data;
  return (
    <div className="page history">
      <div className="page__header">
        <div>
          <p className="eyebrow">EVERYTHING YOU'VE PRACTISED</p>
          <h1 className="page__title">History</h1>
          <p className="page__subtitle">Problems, answers, coaching and interviews, for every career you've practised.</p>
        </div>
      </div>

      <form className="history-filters" role="search" aria-label="Filter history" onSubmit={(e) => e.preventDefault()}>
        <label className="field">
          <span className="field__label">Career</span>
          <select className="select" value={filters.career ?? ""} onChange={(e) => update({ career: e.target.value || undefined })}>
            <option value="">All careers</option>
            {f?.careers.map((c) => <option key={c.value} value={c.value}>{c.label} ({c.count})</option>)}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Activity</span>
          <select className="select" value={filters.type ?? ""} onChange={(e) => update({ type: e.target.value || undefined })}>
            <option value="">All activity</option>
            {f?.types.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Status</span>
          <select className="select" value={filters.status ?? ""} onChange={(e) => update({ status: e.target.value || undefined })}>
            <option value="">Any status</option>
            {f?.statuses.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
        <label className="field">
          <span className="field__label">{filters.career === "coding" ? "Topic" : "Skill"}</span>
          <select className="select" value={filters.skill ?? ""} disabled={!filters.career}
            onChange={(e) => update({ skill: e.target.value || undefined })} aria-describedby={!filters.career ? "skill-help" : undefined}>
            <option value="">{filters.career ? "Any" : "Choose a career first"}</option>
            {f?.skills.map((s) => <option key={s.value} value={s.value}>{s.label}{s.count ? ` (${s.count})` : ""}</option>)}
          </select>
        </label>
        <label className="field">
          <span className="field__label">From</span>
          <input className="input" type="date" value={filters.since ?? ""} max={filters.until} onChange={(e) => update({ since: e.target.value || undefined })} />
        </label>
        <label className="field">
          <span className="field__label">To</span>
          <input className="input" type="date" value={filters.until ?? ""} min={filters.since} onChange={(e) => update({ until: e.target.value || undefined })} />
        </label>
        <label className="field history-filters__search">
          <span className="field__label">Search titles</span>
          <input className="input" type="search" value={search} placeholder="e.g. two sum, assessment" onChange={(e) => setSearch(e.target.value)} />
        </label>
        {hasFilters(params) && (
          <Button type="button" variant="ghost" onClick={() => { setSearch(""); setParams({}, { replace: true }); }}>Clear filters</Button>
        )}
        {!filters.career && <p id="skill-help" className="visually-hidden">Skills and topics belong to one career, so pick a career to filter by skill.</p>}
      </form>

      <p className="subtle history__count" aria-live="polite">
        {activity.isPending ? "Loading…" : `${total} ${total === 1 ? "activity" : "activities"}${hasFilters(params) ? " match" : ""}`}
      </p>

      {activity.isPending ? <LoadingState /> : activity.isError ? <ErrorState error={activity.error} onRetry={() => activity.refetch()} />
        : total === 0 ? (
          hasFilters(params)
            ? <EmptyState title="Nothing matches these filters" action={<Button variant="secondary" onClick={() => { setSearch(""); setParams({}, { replace: true }); }}>Clear filters</Button>}>Try a wider date range or another career.</EmptyState>
            : <EmptyState title="Your practice will appear here" action={<Link className="btn btn--primary btn--md" to="/problems">Start practising</Link>}>Open a problem, answer a question or start a mock interview. Every attempt is saved here with its result.</EmptyState>
        ) : (
          <>
            <ul className="activity-list">{activity.data.items.map((item) => <ActivityRow key={item.id} item={item} />)}</ul>
            {pages > 1 && (
              <nav className="pager" aria-label="History pages">
                <Button variant="secondary" size="sm" disabled={filters.page <= 1} onClick={() => update({ page: String(filters.page - 1) }, false)}>Previous</Button>
                <span className="subtle">Page {filters.page} of {pages}</span>
                <Button variant="secondary" size="sm" disabled={filters.page >= pages} onClick={() => update({ page: String(filters.page + 1) }, false)}>Next</Button>
              </nav>
            )}
          </>
        )}
    </div>
  );
}

function ActivityRow({ item }: { item: ActivityItem }) {
  const location = useLocation();
  return (
    <li>
      <Link to={item.target.href} className="activity-row" state={{ from: location.pathname + location.search, fromLabel: "Back to History" }}>
        <span className="activity-row__main">
          <span className="row activity-row__title">
            <Badge tone={TYPE_TONE[item.type]}>{TYPE_SHORT[item.type]}</Badge>
            <strong>{item.title}</strong>
          </span>
          <span className="subtle activity-row__meta">
            {item.career_title}
            {item.detail ? ` · ${item.detail}` : ""}
            {item.skills.length > 0 ? ` · ${item.skills.slice(0, 3).join(", ")}${item.skills.length > 3 ? "…" : ""}` : ""}
          </span>
        </span>
        <span className="activity-row__side">
          <span className={`activity-status activity-status--${item.status}`}>{item.status_label}</span>
          <time className="subtle" dateTime={item.occurred_at} title={formatDateTime(item.occurred_at)}>{timeAgo(item.occurred_at)}</time>
        </span>
      </Link>
    </li>
  );
}

