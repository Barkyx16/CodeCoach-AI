import { Link } from "react-router-dom";

import { useMyReports } from "@/api/queries";
import { Badge } from "@/components/Badge";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { formatDateTime } from "@/lib/format";

import { CATEGORY_LABEL, STATUS_LABEL, STATUS_TONE } from "./labels";

/** The learner's own reports and what happened to them. Never other people's, never internal notes. */
export function MyReportsPage() {
  const reports = useMyReports();
  return (
    <div className="page reports-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">CONTENT QUALITY</p>
          <h1 className="page__title">Your reports</h1>
          <p className="page__subtitle">Problems you reported with questions, coding problems or feedback, and what happened. Reports are looked at by hand, with no set time; nothing is emailed.</p>
        </div>
      </div>
      {reports.isPending ? <LoadingState label="Loading your reports…" />
        : reports.isError ? <ErrorState error={reports.error} onRetry={() => void reports.refetch()} />
        : reports.data.length === 0 ? (
          <EmptyState title="No reports yet">Use “Report an issue” on a question, a coding problem or the feedback on an answer.</EmptyState>
        ) : (
          <ul className="report-list">
            {reports.data.map((r) => (
              <li key={r.id} className="card stack-sm report-list__item">
                <p className="row report-list__head">
                  <Badge tone={STATUS_TONE[r.status]}>{STATUS_LABEL[r.status]}</Badge>
                  {r.content_href ? <Link to={r.content_href}>{r.content_title}</Link> : <strong>{r.content_title}</strong>}
                </p>
                <p className="subtle">
                  {CATEGORY_LABEL[r.category]}{r.context === "feedback" ? " (about the feedback)" : ""} · version {r.content_version} · reported {formatDateTime(r.created_at)}
                </p>
                {r.details && <p className="report-list__text">{r.details}</p>}
                {r.resolution && <p className="banner banner--info report-list__resolution"><strong>What happened:</strong> {r.resolution}</p>}
              </li>
            ))}
          </ul>
        )}
    </div>
  );
}
