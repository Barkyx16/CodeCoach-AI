import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useCollection, useCollectionMutation, useDeleteCollection } from "@/api/queries";
import type { BatchResult, CollectionItem } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";

import { BulkOutcomes, NoReply, SelectBox } from "./bulk";
import { isDone, useSelection } from "./bulkSelection";
import { useItemKind } from "./labels";

/** One collection: rename, reorder (buttons, keyboard-friendly), remove items, start the practice queue. */
export function CollectionPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const collection = useCollection(id);
  const rename = useCollectionMutation((name: string) => api.renameCollection(id, name));
  const reorder = useCollectionMutation((ids: string[]) => api.reorderCollection(id, ids));
  const remove = useCollectionMutation((itemId: string) => api.removeFromCollection(id, itemId));
  const start = useCollectionMutation((position: number) => api.setQueuePosition(id, position));
  const destroy = useDeleteCollection();
  const itemKind = useItemKind();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [announce, setAnnounce] = useState("");
  // After a move, keep keyboard focus on the same button of the moved item.
  const focusAfter = useRef<{ itemId: string; dir: "up" | "down" } | null>(null);
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  // After a removal the row (and its focused button) is gone: focus the next item's Remove, or the title.
  const focusRemoveAt = useRef<number | null>(null);
  const title = useRef<HTMLHeadingElement>(null);
  // Several at once (docs/BULK_ACTIONS.md): only the rows shown can be picked; removing takes them out
  // of this collection and nothing else (the questions, bookmarks and answers stay).
  const qc = useQueryClient();
  const itemIds = useMemo(() => collection.data?.item_list.map((i) => i.id) ?? [], [collection.data]);
  const selection = useSelection(itemIds);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkResults, setBulkResults] = useState<{ rows: BatchResult[]; titles: Map<string, string> } | null>(null);
  const [bulkLost, setBulkLost] = useState<string[] | null>(null);
  const [bulkError, setBulkError] = useState<unknown>(null);
  const outcomesRef = useRef<HTMLHeadingElement>(null);
  const focusOutcomes = useRef(false);
  useEffect(() => {
    if (!focusOutcomes.current || !bulkResults) return;
    focusOutcomes.current = false;
    outcomesRef.current?.focus();
  }, [bulkResults]);

  useEffect(() => {
    const at = focusRemoveAt.current;
    if (at !== null) {
      focusRemoveAt.current = null;
      const removes = document.querySelectorAll<HTMLButtonElement>(".collection-items [data-remove]");
      (removes[Math.min(at, removes.length - 1)] ?? title.current)?.focus();
    }
    const f = focusAfter.current;
    if (!f) return;
    const el = buttons.current.get(`${f.itemId}:${f.dir}`);
    const fallback = buttons.current.get(`${f.itemId}:${f.dir === "up" ? "down" : "up"}`);
    (el && !el.disabled ? el : fallback)?.focus();
    focusAfter.current = null;
  }, [collection.data]);

  if (collection.isPending) return <LoadingState label="Loading collection…" />;
  if (collection.isError) return <div className="page"><ErrorState error={collection.error} onRetry={() => void collection.refetch()} /></div>;
  const c = collection.data;
  const items = c.item_list;

  async function removeSelected(ids: string[]) {
    setBulkBusy(true);
    setBulkError(null);
    setBulkLost(null);
    const titles = new Map(items.filter((i) => ids.includes(i.id)).map((i) => [i.id, i.title]));
    try {
      const out = await api.batchCollection(id, { remove: ids });
      qc.setQueryData(["me", "collection", id], out.collection);
      void qc.invalidateQueries({ queryKey: ["me", "collections"] });
      void qc.invalidateQueries({ queryKey: ["me", "explore"] });
      setBulkResults({ rows: out.results, titles: new Map([...(bulkResults?.titles ?? []), ...titles]) });
      selection.keep(out.results.filter((r) => !isDone(r)).map((r) => r.key));
      focusOutcomes.current = true; // after the results are on screen (the effect below)
    } catch (e) {
      if (e instanceof ApiError && (e.code === "network_error" || e.status >= 500)) setBulkLost(ids);
      else setBulkError(e);
    } finally {
      setBulkBusy(false);
    }
  }

  function move(item: CollectionItem, dir: "up" | "down") {
    const ids = items.map((i) => i.id);
    const from = ids.indexOf(item.id);
    const to = dir === "up" ? from - 1 : from + 1;
    if (to < 0 || to >= ids.length) return;
    [ids[from], ids[to]] = [ids[to]!, ids[from]!];
    focusAfter.current = { itemId: item.id, dir };
    reorder.mutate(ids, { onSuccess: () => setAnnounce(`Moved “${item.title}” to position ${to + 1} of ${ids.length}.`) });
  }

  function cancelDelete() {
    setConfirming(false);
    // The confirmation closes: put focus back on the button that opened it.
    window.requestAnimationFrame(() => document.getElementById("delete-collection")?.focus());
  }

  async function onRename(e: FormEvent) {
    e.preventDefault();
    const done = await rename.mutateAsync(name.trim() || c.name).catch(() => null);
    if (done) setEditing(false);
  }

  async function onStart() {
    const position = c.queue_started ? c.queue_position : 0;
    const done = await start.mutateAsync(position).catch(() => null);
    if (done) navigate(`/saved/collections/${id}/practice`);
  }

  return (
    <div className="page collection-page">
      <BackLink fallback={{ to: "/saved", label: "All saved items" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">COLLECTION</p>
          {editing ? (
            <form className="row" onSubmit={onRename}>
              <label className="field">
                <span className="field__label">Collection name</span>
                <input className="input" value={name} maxLength={80} autoFocus onChange={(e) => setName(e.target.value)} />
              </label>
              <Button type="submit" size="sm" variant="primary" loading={rename.isPending}>Save name</Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
            </form>
          ) : (
            <h1 className="page__title" ref={title} tabIndex={-1}>{c.name}</h1>
          )}
          <p className="page__subtitle">
            {c.items} {c.items === 1 ? "item" : "items"} · Queue: {c.queue_done} of {c.items} marked done
            {c.queue_started && c.items > 0 ? ` · at item ${c.queue_position + 1}` : ""}
          </p>
          <InlineError error={rename.error} />
        </div>
        <div className="row">
          {!editing && <Button size="sm" variant="ghost" onClick={() => { setName(c.name); setEditing(true); }}>Rename</Button>}
          <Button size="sm" variant="ghost" id="delete-collection" aria-expanded={confirming} onClick={() => setConfirming(true)}>Delete</Button>
          {items.length > 0 && (
            <Button variant="primary" loading={start.isPending} onClick={() => void onStart()}>
              {c.queue_started ? "Continue practice" : "Start this collection"}
            </Button>
          )}
        </div>
      </div>
      <InlineError error={start.error} />

      {confirming && (
        <div className="banner banner--warning stack-sm" role="alertdialog" aria-labelledby="delete-title" aria-describedby="delete-desc"
          onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); cancelDelete(); } }}>
          <strong id="delete-title">Delete “{c.name}”?</strong>
          <p id="delete-desc">This removes the list and its queue progress. The questions, your answers and your bookmarks stay.</p>
          <span className="row">
            <Button variant="danger" size="sm" loading={destroy.isPending} autoFocus
              onClick={() => destroy.mutate(id, { onSuccess: () => navigate("/saved", { replace: true }) })}>Delete collection</Button>
            <Button size="sm" variant="ghost" onClick={cancelDelete}>Cancel</Button>
          </span>
          <InlineError error={destroy.error} />
        </div>
      )}

      <p className="visually-hidden" role="status">{announce}</p>
      {items.length === 0 ? (
        <EmptyState title="This collection is empty" action={<Link className="btn btn--secondary btn--md" to="/problems?view=questions">Browse questions</Link>}>
          Open a question and use “Add to a collection”.
        </EmptyState>
      ) : (
        <div className="stack">
        <div className="bulk-bar" role="group" aria-label="Selected items">
          <label className="checkbox">
            <input type="checkbox" checked={selection.all} onChange={(e) => selection.setAll(e.target.checked)} />
            Select all shown ({items.length})
          </label>
          <span className="subtle" aria-live="polite">{selection.selected.length} of {items.length} selected</span>
          {selection.selected.length > 0 && (
            <span className="bulk-bar__action">
              <Button size="sm" loading={bulkBusy} onClick={() => void removeSelected(selection.selected)}>
                Remove {selection.selected.length} from “{c.name}”
              </Button>
              <Button size="sm" variant="ghost" onClick={() => selection.setAll(false)}>Clear selection</Button>
            </span>
          )}
        </div>
        {selection.selected.length > 0 && (
          <p className="subtle">Removing only takes them out of this collection. The questions stay in the library, and your bookmarks and answers aren't touched.</p>
        )}
        {bulkLost && <NoReply busy={bulkBusy} onRetry={() => void removeSelected(bulkLost)} />}
        <InlineError error={bulkError} />
        {bulkResults && <BulkOutcomes ref={outcomesRef} level={2} results={bulkResults.rows} verb={`removing from “${c.name}”`} titleOf={(k) => bulkResults.titles.get(k) ?? "An item"} />}
        <ol className="collection-items" aria-label="Items in order">
          {items.map((item, index) => (
            <li key={item.id} className={`card collection-item${item.available ? "" : " collection-item--gone"}`}>
              <SelectBox label={`Select: ${item.title}`} checked={selection.isSelected(item.id)} onChange={(on) => selection.toggle(item.id, on)} />
              <span className="collection-item__pos" aria-hidden="true">{index + 1}</span>
              <div className="collection-item__main stack-sm">
                {item.href /* retired items stay readable */
                  ? <Link to={item.href} state={{ from: `/saved/collections/${id}`, fromLabel: `Back to ${c.name}` }}>{item.title}</Link>
                  : <strong>{item.title}</strong>}
                <span className="subtle">{itemKind(item.item_type, item.track)}</span>
                <span className="row">
                  {item.queue_done && <Badge tone="success">Done in queue</Badge>}
                  {item.practiced_since_added && <Badge tone="info">Practiced since added</Badge>}
                </span>
                {!item.available && <p className="banner banner--warning">{item.unavailable_reason}{item.href ? " You can still open it; it isn't used for practice." : ""} Nothing was swapped in for it.</p>}
              </div>
              <div className="collection-item__actions">
                <button type="button" className="btn btn--ghost btn--sm" aria-label={`Move “${item.title}” up`}
                  disabled={index === 0 || reorder.isPending}
                  ref={(el) => { if (el) buttons.current.set(`${item.id}:up`, el); }}
                  onClick={() => move(item, "up")}>↑</button>
                <button type="button" className="btn btn--ghost btn--sm" aria-label={`Move “${item.title}” down`}
                  disabled={index === items.length - 1 || reorder.isPending}
                  ref={(el) => { if (el) buttons.current.set(`${item.id}:down`, el); }}
                  onClick={() => move(item, "down")}>↓</button>
                <Button size="sm" variant="ghost" aria-label={`Remove “${item.title}” from this collection`}
                  data-remove={item.id} loading={remove.isPending && remove.variables === item.id}
                  onClick={() => {
                    focusRemoveAt.current = index;
                    remove.mutate(item.id, {
                      onSuccess: () => setAnnounce(`Removed “${item.title}” from this collection.`),
                      onError: () => { focusRemoveAt.current = null; }, // the row stays; so does focus
                    });
                  }}>Remove</Button>
              </div>
            </li>
          ))}
        </ol>
        </div>
      )}
      {items.length === 0 && bulkResults && <BulkOutcomes ref={outcomesRef} level={2} results={bulkResults.rows} verb={`removing from “${c.name}”`} titleOf={(k) => bulkResults.titles.get(k) ?? "An item"} />}
      <InlineError error={reorder.error ?? remove.error} />
    </div>
  );
}
