import { Link, useLocation } from "react-router-dom";

import { useShares } from "@/api/queries";
import { Badge } from "@/components/Badge";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { formatDateTime, timeAgo } from "@/lib/format";

import { feedbackCount, STATUS_LABEL, STATUS_TONE } from "./shareStatus";

/** Every answer you've shared for feedback, with its link status and how much feedback came back. */
export function SharesPage() {
  const shares = useShares();
  const location = useLocation();
  return (
    <div className="page share-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">FEEDBACK FROM PEOPLE</p>
          <h1 className="page__title">Shared for feedback</h1>
          <p className="page__subtitle">Answers you've shared with a mentor or practice partner, and what they said. Only you see this page.</p>
        </div>
      </div>
      {shares.isPending ? <LoadingState label="Loading your shared answers…" />
        : shares.isError ? <ErrorState error={shares.error} onRetry={() => void shares.refetch()} />
        : shares.data.length === 0 ? (
          <EmptyState title="Nothing shared yet"
            action={<Link className="btn btn--secondary btn--md" to="/problems?view=questions">Go practise</Link>}>
            Open one of your answers (a question you answered, or an interview review) and choose “Ask someone for feedback”.
          </EmptyState>
        ) : (
          <ul className="share-list">
            {shares.data.map((s) => (
              <li key={s.id} className="card share-list__item">
                <Link to={`/shares/${s.id}`} className="share-list__title" state={{ from: location.pathname, fromLabel: "Back to shared answers" }}>{s.question_title}</Link>
                <p className="row share-list__meta">
                  <Badge tone={STATUS_TONE[s.status]}>{STATUS_LABEL[s.status]}</Badge>
                  <span>{feedbackCount(s.feedback_count)}</span>
                  <span className="subtle">{s.career_title} · shared {timeAgo(s.created_at)}</span>
                  {s.status === "active" || s.status === "closed"
                    ? <span className="subtle">expires {formatDateTime(s.expires_at)}</span> : null}
                </p>
              </li>
            ))}
          </ul>
        )}
    </div>
  );
}
