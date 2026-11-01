import { Link } from "react-router-dom";
import { useMySubmissions } from "@/api/queries";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/Badge";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { timeAgo } from "@/lib/format";

export function RecentActivity() {
  const submissions = useMySubmissions({ page: 1, page_size: 4 });
  return (
    <Card className="stack recent-activity">
      <div className="section-heading"><h2 className="section-title">Recent attempts</h2><Link to="/history">View history <span aria-hidden="true">→</span></Link></div>
      {submissions.isPending ? <LoadingState label="Loading recent attempts…" />
        : submissions.isError ? <ErrorState error={submissions.error} onRetry={() => void submissions.refetch()} />
        : submissions.data.items.length === 0 ? <EmptyState title="Your first attempt starts here"><Link to="/problems">Choose a problem</Link></EmptyState>
        : <ul className="recent-list">{submissions.data.items.map((item) => <li key={item.id}><div><Link to={`/problems/${item.problem_slug}`}>{item.problem_title}</Link><span className="subtle">{timeAgo(item.created_at)}</span></div><StatusBadge status={item.status} /></li>)}</ul>}
    </Card>
  );
}
