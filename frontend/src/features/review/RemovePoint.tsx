import { useState } from "react";

import { api } from "@/api/endpoints";
import { useReviewQueueMutation } from "@/api/queries";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";

/**
 * Take one point off a question saved for review (Volume 17, prompt 8; docs/DISPUTES.md, "Saved for
 * several points"), from the review queue or an interview's summary. With other points saved, only
 * this one comes off: the question, its ladder and the other points stay. Its only point is the
 * question's place in the queue: the form says so first (its answers, scores and disputes stay), and
 * the caller offers Undo (`UndoRemoved`), which puts it back as it was, ladder and points.
 */
export function RemovePoint({ itemId, title, point, points, onRemoved }: {
  itemId: string;
  title: string;
  point: string;
  /** The points it's saved for now. */
  points: string[];
  /** The question came out of the queue with its last point. */
  onRemoved(): void;
}) {
  const drop = useReviewQueueMutation(() => api.removeReviewPoint(itemId, point));
  const removeItem = useReviewQueueMutation(() => api.removeReview(itemId));
  const [confirming, setConfirming] = useState(false);
  if (confirming) {
    return (
      <div className="banner banner--warning stack-sm" role="group" aria-label={`Remove the point “${point}”`}>
        <p>“{point}” is the only point “{title}” is saved for, so removing it takes the question out of your review queue. Its answers, scores and any disputes stay.</p>
        <span className="row">
          <Button size="sm" variant="danger" loading={removeItem.isPending}
            onClick={() => removeItem.mutate(undefined, { onSuccess: () => { setConfirming(false); onRemoved(); } })}>
            Take it out of the queue
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>Keep it</Button>
        </span>
        <InlineError error={removeItem.error} />
      </div>
    );
  }
  return (
    <>
      <Button size="sm" variant="ghost" loading={drop.isPending} aria-label={`Remove the point “${point}”`}
        onClick={() => (points.length <= 1 ? setConfirming(true) : drop.mutate(undefined))}>
        Remove this point
      </Button>
      <InlineError error={drop.error} />
    </>
  );
}

/** After a question came out of the queue with its last point: say so, and put it back as it was. */
export function UndoRemoved({ itemId, title, onDone }: { itemId: string; title: string; onDone(): void }) {
  const restore = useReviewQueueMutation(() => api.restoreReview(itemId));
  return (
    <div className="banner banner--info row" role="status">
      <span>Took “{title}” out of your review queue.</span>
      <Button size="sm" variant="secondary" loading={restore.isPending} onClick={() => restore.mutate(undefined, { onSuccess: onDone })}>Undo</Button>
      <InlineError error={restore.error} />
    </div>
  );
}
