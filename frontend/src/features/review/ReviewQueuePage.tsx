import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useReviewQueue, useReviewQueueMutation } from "@/api/queries";
import type { ReviewQueueItem } from "@/api/types";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";

/** Questions saved for spaced review: what's due, why, and when the rest come back. */
export function ReviewQueuePage() {
  const queue = useReviewQueue();
  if (queue.isPending) return <LoadingState label="Loading your review queue…" />;
  if (queue.isError) return <div className="page"><ErrorState error={queue.error} onRetry={() => void queue.refetch()} /></div>;
  const q = queue.data;
  return (
    <div className="page review-queue">
      <div className="page__header">
        <div>
          <p className="eyebrow">SPACED REVIEW</p>
          <h1 className="page__title">Review queue</h1>
          <p className="page__subtitle">{q.note} Gaps follow a fixed ladder: {q.ladder_days.join(", ")} days.</p>
        </div>
      </div>
      {q.due.length + q.upcoming.length === 0 ? (
        <EmptyState title="Nothing saved for review" action={<Link className="btn btn--primary btn--md" to="/history?type=interview">Review an interview</Link>}>
          After an interview, use "Save for later review" on a question to bring it back on a schedule.
        </EmptyState>
      ) : (
        <>
          <section className="stack" aria-labelledby="due-title">
            <h2 className="section-title" id="due-title">Due now ({q.due.length})</h2>
            {q.due.length === 0 ? <p className="subtle">Nothing due. The next one is listed below.</p> : <ul className="target-list">{q.due.map((i) => <QueueRow key={i.id} item={i} />)}</ul>}
          </section>
          {q.upcoming.length > 0 && (
            <section className="stack" aria-labelledby="upcoming-title">
              <h2 className="section-title" id="upcoming-title">Coming up ({q.upcoming.length})</h2>
              <ul className="target-list">{q.upcoming.map((i) => <QueueRow key={i.id} item={i} />)}</ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function QueueRow({ item }: { item: ReviewQueueItem }) {
  const snooze = useReviewQueueMutation((days: 1 | 3 | 7) => api.snoozeReview(item.id, days));
  const remove = useReviewQueueMutation(() => api.removeReview(item.id));
  return (
    <li className="card stack queue-row" aria-label={item.title}>
      <div className="row queue-row__head">
        <strong>{item.title}</strong>
        <span className="subtle">{item.career_title}{item.last_score !== null && item.last_score !== undefined ? ` · last ${item.last_score}/100` : ""}</span>
      </div>
      <p className="subtle">{item.why}</p>
      <div className="row queue-row__actions">
        <Link className="btn btn--primary btn--sm" to={item.href} state={{ from: "/reviews", fromLabel: "Back to the review queue" }}>Answer it now</Link>
        {[1, 3, 7].map((d) => (
          <Button key={d} size="sm" variant="ghost" loading={snooze.isPending && snooze.variables === d} onClick={() => snooze.mutate(d as 1 | 3 | 7)}>
            Snooze {d} {d === 1 ? "day" : "days"}
          </Button>
        ))}
        <Button size="sm" variant="ghost" loading={remove.isPending} onClick={() => remove.mutate(undefined)}>Remove</Button>
      </div>
      <InlineError error={snooze.error ?? remove.error} />
    </li>
  );
}
