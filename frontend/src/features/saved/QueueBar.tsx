import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useCollection } from "@/api/queries";
import type { SavedItemRef } from "@/api/types";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";

import { queueHref } from "./labels";

/** Shown on a question/problem opened from a practice queue (?queue=<collection id>). */
export function QueueBar({ item }: { item: SavedItemRef }) {
  const [params] = useSearchParams();
  const queueId = params.get("queue") ?? "";
  const collection = useCollection(queueId, Boolean(queueId));
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  if (!queueId || !collection.data) return null;
  const c = collection.data;
  const index = c.item_list.findIndex((i) => i.item_type === item.item_type && i.track === (item.track ?? "") && i.ref_id === item.ref_id);
  if (index < 0) return null;
  const here = c.item_list[index]!;
  const next = c.item_list[index + 1];
  const queuePage = `/saved/collections/${c.id}/practice`;

  async function doneAndNext() {
    setBusy(true);
    setError(null);
    try {
      if (!here.queue_done) await api.markQueueDone(c.id, here.id, true);
      const fresh = await api.setQueuePosition(c.id, next ? index + 1 : index);
      qc.setQueryData(["me", "collection", c.id], fresh);
      void qc.invalidateQueries({ queryKey: ["me", "collections"] });
      const nextHref = next ? queueHref(fresh, fresh.item_list[index + 1]!) : null;
      // The next item says "Back to the queue" and opens the queue (not the item before it). The
      // last one goes to the queue itself, which shows its own way back to the collection.
      navigate(nextHref ?? queuePage, nextHref ? { state: { from: queuePage, fromLabel: "Back to the queue", backVia: "link" } } : undefined);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="queue-bar" role="region" aria-label="Practice queue">
      <span><strong>{c.name}</strong> · item {index + 1} of {c.item_list.length}{here.queue_done ? " · done" : ""}</span>
      <span className="row">
        <Link to={queuePage}>Back to the queue</Link>
        <Button size="sm" variant="primary" loading={busy} onClick={() => void doneAndNext()}>
          {next ? "Mark done and go to next" : "Mark done and finish"}
        </Button>
      </span>
      <InlineError error={error} />
    </div>
  );
}
