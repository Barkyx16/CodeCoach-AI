import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/endpoints";
import { useActivity, useActivityFacets } from "@/api/queries";
import type { ActivityItem, ConditionsOut } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useScrollMemory } from "@/hooks/useScrollMemory";
import { conditionsSummary } from "@/features/conditions/summary";
import { formatDateTime, timeAgo } from "@/lib/format";

import { PAGE_SIZE, filtersFromParams, hasFilters } from "./historyState";

const TYPE_TONE: Record<ActivityItem["type"], string> = {
  problem_opened: "neutral",
  code_submission: "info",
  coaching: "info",
  written_answer: "success",
  interview: "warning",
  drill_attempt: "success",
  whiteboard_attempt: "success",
  work_sample_attempt: "success",
  scenario_attempt: "success",
  code_review_attempt: "info",
  comparison_attempt: "success",
  test_design_run: "info",
};
const TYPE_SHORT: Record<ActivityItem["type"], string> = {
  problem_opened: "Opened",
  code_submission: "Submission",
  coaching: "Coaching",
  written_answer: "Answer",
  interview: "Interview",
  drill_attempt: "Drill",
  whiteboard_attempt: "Whiteboard",
  work_sample_attempt: "Work sample",
  scenario_attempt: "Scenario",
  code_review_attempt: "Code review",
  comparison_attempt: "Samples compared",
  test_design_run: "Test design",
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
  // The in-app help before each attempt on this page (docs/ATTEMPT_CONDITIONS.md): one request for
  // the rows shown, so the list itself stays as it was.
  const items = activity.data?.items ?? [];
  const submissionIds = items.flatMap((i) => (i.type === "code_submission" && i.target.submission_id ? [i.target.submission_id] : []));
  const answerIds = items.flatMap((i) => (i.type === "written_answer" && i.target.answer_id ? [i.target.answer_id] : []));
  // Coding interviews: a career interview isn't described as a whole (its answers are), so it's absent.
  const interviewIds = items.flatMap((i) => (i.type === "interview" && i.target.interview_id ? [i.target.interview_id] : []));
  // Drills, whiteboard designs and work samples (Volume 16, prompt 6): only asked for when on the page.
  const attemptsOf = (type: ActivityItem["type"]) => items.flatMap((i) => (i.type === type && i.target.attempt_id ? [i.target.attempt_id] : []));
  const drillIds = attemptsOf("drill_attempt");
  const whiteboardIds = attemptsOf("whiteboard_attempt");
  const workSampleIds = attemptsOf("work_sample_attempt");
  // Scenario runs, code reviews and sample-answer comparisons (Volume 17, prompt 2).
  const scenarioIds = attemptsOf("scenario_attempt");
  const codeReviewIds = attemptsOf("code_review_attempt");
  const comparisonIds = attemptsOf("comparison_attempt");
  const practiceIds = {
    ...(drillIds.length ? { drill_attempt_ids: drillIds } : {}),
    ...(whiteboardIds.length ? { whiteboard_attempt_ids: whiteboardIds } : {}),
    ...(workSampleIds.length ? { work_sample_attempt_ids: workSampleIds } : {}),
    ...(scenarioIds.length ? { scenario_attempt_ids: scenarioIds } : {}),
    ...(codeReviewIds.length ? { code_review_attempt_ids: codeReviewIds } : {}),
    ...(comparisonIds.length ? { comparison_attempt_ids: comparisonIds } : {}),
  };
  const practiceCount = Object.values(practiceIds).reduce((n, ids) => n + ids.length, 0);
  const conditions = useQuery({
    queryKey: ["me", "attempt-conditions", submissionIds, answerIds, interviewIds, practiceIds],
    queryFn: () => api.attemptConditions({ submission_ids: submissionIds, answer_ids: answerIds, interview_ids: interviewIds, ...practiceIds }),
    enabled: submissionIds.length + answerIds.length + interviewIds.length + practiceCount > 0,
  });
  // Back from an item: the same scroll position, and focus on the item it came back from.
  useScrollMemory(Boolean(activity.data) && !activity.isPlaceholderData && !activity.isFetching);

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
            <ul className="activity-list">{activity.data.items.map((item) => <ActivityRow key={item.id} item={item} conditions={conditions.data ? labelsFor(conditions.data, item) : null} />)}</ul>
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

function labelsFor(found: ConditionsOut, item: ActivityItem): string | null {
  const c = item.type === "code_submission" ? found.submissions[item.target.submission_id ?? ""]
    : item.type === "written_answer" ? found.answers[item.target.answer_id ?? ""]
      : item.type === "interview" ? found.interviews?.[item.target.interview_id ?? ""]
        : item.type === "drill_attempt" ? found.drill_attempts?.[item.target.attempt_id ?? ""]
          : item.type === "whiteboard_attempt" ? found.whiteboard_attempts?.[item.target.attempt_id ?? ""]
            : item.type === "work_sample_attempt" ? found.work_sample_attempts?.[item.target.attempt_id ?? ""]
              : item.type === "scenario_attempt" ? found.scenario_attempts?.[item.target.attempt_id ?? ""]
                : item.type === "code_review_attempt" ? found.code_review_attempts?.[item.target.attempt_id ?? ""]
                  : item.type === "comparison_attempt" ? found.comparison_attempts?.[item.target.attempt_id ?? ""] : undefined;
  return conditionsSummary(c);
}

function ActivityRow({ item, conditions }: { item: ActivityItem; conditions: string | null }) {
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
            {conditions ? ` · In-app help: ${conditions}` : ""}
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

