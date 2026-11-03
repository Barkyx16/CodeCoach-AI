import { Link, useParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useCollection, useCollectionMutation } from "@/api/queries";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";

import { queueHref, useItemKind } from "./labels";

/**
 * A collection practiced in order. Position and "done" marks belong to this queue only; mastery
 * still comes from your scored answers, which this page reports separately.
 */
export function QueuePage() {
  const { id = "" } = useParams();
  const collection = useCollection(id);
  const go = useCollectionMutation((position: number) => api.setQueuePosition(id, position));
  const mark = useCollectionMutation(({ itemId, done }: { itemId: string; done: boolean }) => api.markQueueDone(id, itemId, done));
  const remove = useCollectionMutation((itemId: string) => api.removeFromCollection(id, itemId));
  const itemKind = useItemKind();

  if (collection.isPending) return <LoadingState label="Loading practice queue…" />;
  if (collection.isError) return <div className="page"><ErrorState error={collection.error} onRetry={() => void collection.refetch()} /></div>;
  const c = collection.data;
  const items = c.item_list;
  if (items.length === 0) {
    return (
      <div className="page">
        <EmptyState pageTitle title="This collection is empty" action={<Link className="btn btn--secondary btn--md" to={`/saved/collections/${id}`}>Back to the collection</Link>}>
          Add questions to it first.
        </EmptyState>
      </div>
    );
  }
  const position = Math.min(c.queue_position, items.length - 1);
  const current = items[position]!;
  const href = queueHref(c, current);
  const practiced = items.filter((i) => i.practiced_since_added).length;
  const allDone = c.queue_done === items.length;

  return (
    <div className="page queue-page">
      <BackLink fallback={{ to: `/saved/collections/${id}`, label: `Back to ${c.name}` }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">PRACTICE QUEUE</p>
          <h1 className="page__title">{c.name}</h1>
          <p className="page__subtitle">Item {position + 1} of {items.length}</p>
        </div>
      </div>

      <section className="queue-progress" aria-label="Queue progress">
        <div>
          <strong>{c.queue_done} of {items.length}</strong> marked done in this queue
          <progress aria-label="Queue items marked done" value={c.queue_done} max={items.length} />
        </div>
        <p className="subtle">
          {practiced} of {items.length} practiced since you added them. “Done” only moves this queue along;
          your scores and mastery come from your answers.
        </p>
      </section>

      {allDone && <p className="banner banner--success" role="status">You've marked every item done. Your answers are in History.</p>}

      <Card className="stack queue-current" aria-labelledby="current-title">
        <p className="eyebrow">NOW · {position + 1} OF {items.length}</p>
        <h2 className="section-title" id="current-title">{current.title}</h2>
        <p className="subtle">{itemKind(current.item_type, current.track)}</p>
        <span className="row">
          {current.queue_done && <Badge tone="success">Done in queue</Badge>}
          {current.practiced_since_added && <Badge tone="info">Practiced since added</Badge>}
        </span>
        {!current.available && (
          <div className="banner banner--warning stack-sm">
            <p>{current.unavailable_reason} Nothing was swapped in for it.</p>
            <span className="row">
              <Button size="sm" loading={remove.isPending} onClick={() => remove.mutate(current.id)}>Remove it from this collection</Button>
            </span>
          </div>
        )}
        <div className="row">
          {href && (
            <Link className="btn btn--primary btn--md" to={href} state={{ from: `/saved/collections/${id}/practice`, fromLabel: "Back to the queue" }}>
              {current.item_type === "question" ? "Answer this question" : "Solve this problem"}
            </Link>
          )}
          <Button loading={mark.isPending} aria-pressed={current.queue_done}
            onClick={() => mark.mutate({ itemId: current.id, done: !current.queue_done })}>
            {current.queue_done ? "Marked done" : "Mark done"}
          </Button>
        </div>
        <div className="row queue-current__nav">
          <Button size="sm" variant="ghost" disabled={position === 0 || go.isPending} onClick={() => go.mutate(position - 1)}>Previous</Button>
          <Button size="sm" variant="ghost" disabled={position === items.length - 1 || go.isPending} onClick={() => go.mutate(position + 1)}>Next</Button>
        </div>
        <InlineError error={go.error ?? mark.error ?? remove.error} />
      </Card>

      <section className="stack" aria-labelledby="queue-list-title">
        <h2 className="section-title" id="queue-list-title">Everything in this queue</h2>
        <ol className="queue-list">
          {items.map((item, i) => (
            <li key={item.id} aria-current={i === position ? "step" : undefined}>
              <button type="button" className="queue-list__item" onClick={() => go.mutate(i)} disabled={i === position}>
                <span>{i + 1}. {item.title}</span>
                <span className="subtle">{item.queue_done ? "Done" : item.available ? "To do" : "Unavailable"}</span>
              </button>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
