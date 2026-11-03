import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import type { ReportStatusValue } from "@/api/types";
import { Badge } from "@/components/Badge";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { Tabs } from "@/components/Tabs";
import { formatDateTime } from "@/lib/format";

import { CATEGORY_LABEL, STATUS_LABEL, STATUS_TONE } from "@/features/content/labels";

const FILTERS = [
  { id: "open", label: "Open" },
  { id: "resolved", label: "Resolved" },
  { id: "not_actionable", label: "Not actionable" },
  { id: "all", label: "All" },
] as const;
type Filter = (typeof FILTERS)[number]["id"];

/** Triage: reports grouped by the content they're about, likely duplicates nested under the first. */
export function AdminReportsPage() {
  const [params, setParams] = useSearchParams();
  const filter = (FILTERS.find((f) => f.id === params.get("status"))?.id ?? "open") as Filter;
  const groups = useQuery({ queryKey: ["admin", "reports", filter], queryFn: () => api.adminReports(filter === "all" ? undefined : filter), staleTime: 0 });
  return (
    <div className="page admin-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">ADMIN · CONTENT QUALITY</p>
          <h1 className="page__title">Reports</h1>
          <p className="page__subtitle">Learners' reports, grouped by question or problem. Report text is shown exactly as written, as plain text.</p>
        </div>
      </div>
      <Tabs label="Status" tabs={FILTERS.map((f) => ({ id: f.id, label: f.label }))} value={filter}
        onChange={(id) => setParams(id === "open" ? {} : { status: id }, { replace: true })}>
        {groups.isPending ? <LoadingState label="Loading reports…" />
          : groups.isError ? <ErrorState error={groups.error} onRetry={() => void groups.refetch()} />
          : groups.data.length === 0 ? <EmptyState title="Nothing here">No reports with this status.</EmptyState>
          : (
            <ul className="admin-groups">
              {groups.data.map((g) => (
                <li key={`${g.content_type}:${g.content_id}`} className="card stack-sm">
                  <h2 className="section-title admin-groups__title">
                    {g.content_title} <span className="subtle">({g.content_type === "question" ? "question" : "problem"} · {g.content_id})</span>
                  </h2>
                  <p className="subtle">{g.open_count} open · {g.reports.length} in this list</p>
                  <ul className="admin-reports">
                    {g.reports.map((r) => (
                      <li key={r.id} className={r.duplicate_of ? "admin-reports__dup" : undefined}>
                        <Link to={`/admin/reports/${r.id}`}>{CATEGORY_LABEL[r.category]}{r.context === "feedback" ? " (feedback)" : ""}</Link>{" "}
                        <Badge tone={STATUS_TONE[r.status as ReportStatusValue]}>{STATUS_LABEL[r.status as ReportStatusValue]}</Badge>{" "}
                        <span className="subtle">v{r.content_version}{r.content_version < r.current_version ? ` (now v${r.current_version})` : ""} · {r.reporter} · {formatDateTime(r.created_at)}{r.duplicate_of ? " · likely duplicate" : ""}</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
      </Tabs>
    </div>
  );
}
