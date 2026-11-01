import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useAIHistory, useInterviews, useMySubmissions } from "@/api/queries";
import type { AIHistoryAction, AIHistoryItem, CodeReview, FailureExplanation } from "@/api/types";
import { Badge, StatusBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { InterviewRow } from "@/features/interview/InterviewStartPage";
import { ReviewResult } from "@/features/workspace/CoachPanel";
import { FailureExplanationView } from "@/features/workspace/FailureExplanation";
import { formatDateTime, timeAgo } from "@/lib/format";

const PAGE_SIZE = 15;

export function HistoryPage() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab = raw === "ai" || raw === "interviews" ? raw : "submissions";
  return (
    <div className="page history">
      <div className="page__header">
        <div>
          <h1 className="page__title">History</h1>
          <p className="page__subtitle">Every attempt and every piece of AI feedback, saved.</p>
        </div>
      </div>
      <div className="tabs" role="tablist" aria-label="History type">
        <button type="button" role="tab" aria-selected={tab === "submissions"} className={`tab${tab === "submissions" ? " tab--active" : ""}`}
          onClick={() => setParams({}, { replace: true })}>Submissions</button>
        <button type="button" role="tab" aria-selected={tab === "ai"} className={`tab${tab === "ai" ? " tab--active" : ""}`}
          onClick={() => setParams({ tab: "ai" }, { replace: true })}>AI feedback</button>
        <button type="button" role="tab" aria-selected={tab === "interviews"} className={`tab${tab === "interviews" ? " tab--active" : ""}`}
          onClick={() => setParams({ tab: "interviews" }, { replace: true })}>Interviews</button>
      </div>
      <div role="tabpanel">
        {tab === "ai" ? <AIFeedbackList /> : tab === "interviews" ? <InterviewList /> : <SubmissionList />}
      </div>
    </div>
  );
}

function Pager({ page, total, onPage }: { page: number; total: number; onPage(p: number): void }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (pages <= 1) return null;
  return (
    <nav className="pagination" aria-label="Pagination">
      <Button size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
      <span className="subtle">Page {page} of {pages}</span>
      <Button size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</Button>
    </nav>
  );
}

function SubmissionList() {
  const [page, setPage] = useState(1);
  const q = useMySubmissions({ page, page_size: PAGE_SIZE });
  if (q.isPending) return <LoadingState />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (q.data.total === 0) {
    return <EmptyState title="No submissions yet" action={<Link to="/problems">Find a problem</Link>}>Your attempts will appear here.</EmptyState>;
  }
  return (
    <>
      <table className="data-table history__table">
        <thead>
          <tr><th scope="col">Problem</th><th scope="col">Status</th><th scope="col">Submitted</th><th scope="col">Runtime</th></tr>
        </thead>
        <tbody>
          {q.data.items.map((s) => (
            <tr key={s.id}>
              <td><Link to={`/problems/${s.problem_slug}`}>{s.problem_title}</Link></td>
              <td><StatusBadge status={s.status} /></td>
              <td title={formatDateTime(s.created_at)}>{timeAgo(s.created_at)}</td>
              <td>{s.duration_ms !== null && s.duration_ms !== undefined ? `${s.duration_ms} ms` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pager page={page} total={q.data.total} onPage={setPage} />
    </>
  );
}

function AIFeedbackList() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState<"" | AIHistoryAction>("");
  const q = useAIHistory({ page, page_size: PAGE_SIZE, action: action || undefined });
  return (
    <div className="stack">
      <label className="field history__filter">
        <span className="visually-hidden">Filter feedback type</span>
        <select className="select" value={action} onChange={(e) => { setAction(e.target.value as typeof action); setPage(1); }}>
          <option value="">All feedback</option>
          <option value="hint">Hints</option>
          <option value="review">Reviews</option>
          <option value="explain_failure">Failure explanations</option>
        </select>
      </label>
      {q.isPending ? <LoadingState /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> :
        q.data.total === 0 ? <EmptyState title="No AI feedback yet">Ask for a hint or a review in any problem.</EmptyState> : (
          <>
            <ul className="feedback-list">{q.data.items.map((item) => <FeedbackItem key={item.id} item={item} />)}</ul>
            <Pager page={page} total={q.data.total} onPage={setPage} />
          </>
        )}
    </div>
  );
}

function FeedbackItem({ item }: { item: AIHistoryItem }) {
  const [open, setOpen] = useState(false);
  const response = (item.response ?? {}) as Record<string, unknown>;
  const title = item.action === "hint" ? `Hint level ${item.hint_level ?? "?"}`
    : item.action === "explain_failure" ? "Failure explained" : "Code review";
  const tone = item.action === "hint" ? "info" : item.action === "explain_failure" ? "warning" : "success";
  return (
    <li className="feedback card">
      <button type="button" className="feedback__toggle" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="row">
          <Badge tone={tone}>{title}</Badge>
          <strong>{item.problem_title}</strong>
        </span>
        <span className="subtle" title={formatDateTime(item.created_at)}>{timeAgo(item.created_at)}</span>
      </button>
      {open && (
        <div className="feedback__body">
          {item.action === "hint" ? (
            <p>{String(response.hint ?? "")}</p>
          ) : item.action === "explain_failure" ? (
            <FailureExplanationView data={{
              submission_id: "", status: "", cached: true, provider: item.provider,
              explanation: response as unknown as FailureExplanation,
              disclaimer: "Based only on the public tests and compiler output.",
            }} />
          ) : (
            <ReviewResult data={{
              review: response as unknown as CodeReview, provider: item.provider, expected_complexity: null,
              judge_status: null, disclaimer: "AI feedback can be wrong. Pass/fail comes only from the test judge.",
            }} />
          )}
          <p className="subtle">Answered by: {item.provider}</p>
        </div>
      )}
    </li>
  );
}

function InterviewList() {
  const [page, setPage] = useState(1);
  const q = useInterviews({ page, page_size: PAGE_SIZE });
  if (q.isPending) return <LoadingState />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (q.data.total === 0) {
    return <EmptyState title="No interviews yet" action={<Link to="/interviews">Start a mock interview</Link>}>Your mock interviews and their feedback will appear here.</EmptyState>;
  }
  return (
    <>
      <ul className="interview-list">{q.data.items.map((iv) => <InterviewRow key={iv.id} iv={iv} />)}</ul>
      <Pager page={page} total={q.data.total} onPage={setPage} />
    </>
  );
}
