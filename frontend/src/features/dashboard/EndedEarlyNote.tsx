import { useState } from "react";
import { Link } from "react-router-dom";

import { useInterviews } from "@/api/queries";
import { Icon } from "@/components/Icon";

const RECENT_DAYS = 14;

/**
 * When the learner's latest question round ended before every question was answered (they ended
 * it, or its time ran out), points to what the app supports afterwards: the round's review, which
 * lists the questions not reached and lets them answer each one as a retry. It doesn't claim the
 * round can be resumed or call it completed; a new round is a separate, explicit choice.
 */
export function EndedEarlyNote() {
  const rounds = useInterviews({ page: 1, page_size: 5 });
  const [now] = useState(() => Date.now()); // "recent" is judged when the dashboard opens
  const latest = rounds.data?.items[0];
  if (!latest || latest.kind !== "questions" || (latest.status !== "abandoned" && latest.status !== "expired")) return null;
  const ended = latest.ended_at ?? latest.started_at;
  if (now - new Date(ended).getTime() > RECENT_DAYS * 86_400_000) return null;
  const why = latest.status === "expired" ? "ran out of time" : "ended early";
  return (
    <aside className="ended-early" aria-labelledby="ended-early-title">
      <span className="ended-early__icon" aria-hidden="true"><Icon name="clock" size={18} /></span>
      <div className="ended-early__text">
        <h2 className="ended-early__title" id="ended-early-title">Your last mock interview {why}</h2>
        <p className="subtle">
          It stays recorded as {why === "ran out of time" ? "out of time" : "ended early"}, with the answers you gave.
          Its review lists the questions you didn't reach, and you can answer each one there.
        </p>
      </div>
      <Link className="btn btn--secondary btn--md" to={`/interviews/${latest.id}`}>Review it <Icon name="arrow" size={15} /></Link>
    </aside>
  );
}
