import { ScheduleLink } from "@/features/schedule/ScheduleLink";
import { createContext, useContext, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useReviewQueue, useReviewQueueMutation } from "@/api/queries";
import type { ReviewQueueItem } from "@/api/types";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";
import { formatDateTime } from "@/lib/format";

import { RemovePoint, UndoRemoved } from "./RemovePoint";

/** A question that came out of the queue with its last point, for the page's Undo (its row is gone). */
const Removed = createContext<(item: { id: string; title: string }) => void>(() => undefined);

/** Questions saved for spaced review: what's due, why, and when the rest come back. */
export function ReviewQueuePage() {
  const queue = useReviewQueue();
  const [removed, setRemoved] = useState<{ id: string; title: string } | null>(null);
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
      {removed && <UndoRemoved itemId={removed.id} title={removed.title} onDone={() => setRemoved(null)} />}
      <Removed.Provider value={setRemoved}>
      {q.due.length + q.upcoming.length + (q.disputed ?? []).length === 0 ? (
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
          {(q.disputed ?? []).length > 0 && (
            <section className="stack" aria-labelledby="disputed-title">
              <h2 className="section-title" id="disputed-title">You disputed this ({(q.disputed ?? []).length})</h2>
              <p className="subtle">Not scheduled: the only reason each is here is feedback you disputed. Count that feedback again to put it back, or answer it any time. The feedback itself is unchanged.</p>
              <ul className="target-list">{(q.disputed ?? []).map((i) => <DisputedRow key={i.id} item={i} />)}</ul>
            </section>
          )}
        </>
      )}
      </Removed.Provider>
    </div>
  );
}

function DisputedRow({ item }: { item: ReviewQueueItem }) {
  const remove = useReviewQueueMutation(() => api.removeReview(item.id));
  return (
    <li className="card stack queue-row" aria-label={item.title}>
      <div className="row queue-row__head">
        <strong>{item.title}</strong>
        <span className="subtle">{item.career_title}</span>
      </div>
      <SavedFor item={item} />
      <p className="subtle">{item.why}</p>
      <div className="row queue-row__actions">
        {item.dispute && <Link className="btn btn--secondary btn--sm" to={item.dispute.href}>Count it again (see the dispute)</Link>}
        <Link className="btn btn--ghost btn--sm" to={item.href} state={{ from: "/reviews", fromLabel: "Back to the review queue" }}>Answer it anyway</Link>
        <Button size="sm" variant="ghost" loading={remove.isPending} onClick={() => remove.mutate(undefined)}>Remove</Button>
      </div>
      <InlineError error={remove.error} />
    </li>
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
      <SavedFor item={item} />
      <p className="subtle">{item.why}</p>
      <div className="row queue-row__actions">
        <Link className="btn btn--primary btn--sm" to={item.href} state={{ from: "/reviews", fromLabel: "Back to the review queue" }}>Answer it now</Link>
        {[1, 3, 7].map((d) => (
          <Button key={d} size="sm" variant="ghost" loading={snooze.isPending && snooze.variables === d} onClick={() => snooze.mutate(d as 1 | 3 | 7)}>
            Snooze {d} {d === 1 ? "day" : "days"}
          </Button>
        ))}
        <Button size="sm" variant="ghost" loading={remove.isPending} onClick={() => remove.mutate(undefined)}>Remove</Button>
        <ScheduleLink kind="review_item" refId={item.id} title={`Review: ${item.title}`} />
      </div>
      <InlineError error={snooze.error ?? remove.error} />
    </li>
  );
}

/** The points it's saved for (Volume 16, prompt 5), each removable on its own (Volume 17, prompt 8):
 * with others saved, only that point comes off; its only point takes the question out, after saying so,
 * with Undo. The points taken off are listed with when, since a recount may name them. */
function SavedFor({ item }: { item: ReviewQueueItem }) {
  const points = item.points?.length ? item.points : item.criterion ? [item.criterion] : [];
  const onRemoved = useContext(Removed);
  const history = item.removed_points ?? [];
  if (points.length === 0 && history.length === 0) return null;
  return (
    <div className="stack-sm">
      {points.length === 1 ? (
        <div className="row">
          <span className="subtle">Saved for “{points[0]}”.</span>
          <RemovePoint itemId={item.id} title={item.title} point={points[0]!} points={points} onRemoved={() => onRemoved({ id: item.id, title: item.title })} />
        </div>
      ) : points.length > 1 && (
        <>
          <p className="subtle">Saved for {points.length} points:</p>
          <ul className="mini-list" aria-label={`Points “${item.title}” is saved for`}>
            {points.map((p) => (
              <li key={p} className="row">
                <span>“{p}”</span>
                <RemovePoint itemId={item.id} title={item.title} point={p} points={points} onRemoved={() => onRemoved({ id: item.id, title: item.title })} />
              </li>
            ))}
          </ul>
        </>
      )}
      {history.length > 0 && (
        <p className="subtle">{history.map((h) => `“${h.point}” was removed on ${formatDateTime(h.removed_at)}.`).join(" ")}{item.released ? ` ${item.released}` : ""}</p>
      )}
    </div>
  );
}
