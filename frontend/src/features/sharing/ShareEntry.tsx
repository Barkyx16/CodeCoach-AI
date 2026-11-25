import { Link, useLocation } from "react-router-dom";

import { useShares } from "@/api/queries";

/** "Ask someone for feedback" on one of your answers, and how much people have said so far. */
export function ShareEntry({ answerId, fromLabel }: { answerId: string; fromLabel: string }) {
  const location = useLocation();
  const shares = useShares(answerId);
  const count = shares.data?.length ?? 0;
  const responses = shares.data?.reduce((n, s) => n + s.feedback_count, 0) ?? 0;
  return (
    <div className="row share-entry">
      <Link className="btn btn--secondary btn--sm" to={`/share/new?answer=${encodeURIComponent(answerId)}`}
        state={{ from: location.pathname + location.search, fromLabel }}>
        Ask someone for feedback
      </Link>
      {count > 0 && (
        <Link to="/shares">
          Shared {count} {count === 1 ? "time" : "times"} · {responses} {responses === 1 ? "response" : "responses"} from people
        </Link>
      )}
    </div>
  );
}
