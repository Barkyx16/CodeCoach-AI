import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useBookmarks, useCollectionMutation, useCollections, useToggleBookmark } from "@/api/queries";
import type { BatchResult, Bookmark } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";
import { timeAgo } from "@/lib/format";

import { BulkOutcomes, NoReply, SelectBox } from "./bulk";
import { BATCH_LIMIT, isDone, useSelection } from "./bulkSelection";
import { useItemKind } from "./labels";

const markKey = (b: { item_type: string; track: string; ref_id: string }) => `${b.item_type}:${b.item_type === "question" ? b.track : ""}:${b.ref_id}`;

/** Your bookmarks and private collections. Nothing here is visible to anyone else. */
export function SavedPage() {
  const navigate = useNavigate();
  const collections = useCollections();
  const bookmarks = useBookmarks();
  const create = useCollectionMutation((name: string) => api.createCollection(name));
  const removeMark = useToggleBookmark();
  const marksHeading = useRef<HTMLHeadingElement>(null);
  const [marksNote, setMarksNote] = useState("");
  const { user } = useAuth();

  function removeBookmark(mark: Bookmark) {
    setMarksNote("");
    removeMark.mutate({ ref: { item_type: mark.item_type, track: mark.track, ref_id: mark.ref_id }, on: false }, {
      onSuccess: () => setMarksNote(`Removed bookmark: ${mark.title}.`),
    });
    marksHeading.current?.focus(); // the row disappears at once
  }
  const [name, setName] = useState("");

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    const c = await create.mutateAsync(name.trim() || "Untitled").catch(() => null);
    if (c) {
      setName("");
      navigate(`/saved/collections/${c.id}`);
    }
  }

  return (
    <div className="page saved-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">SAVED</p>
          <h1 className="page__title">Bookmarks and collections</h1>
          <p className="page__subtitle">Private to you. Collections are ordered lists you can practice as a queue.</p>
        </div>
      </div>

      <section className="stack" aria-labelledby="collections-title">
        <h2 className="section-title" id="collections-title"><Icon name="list" size={16} />Collections</h2>
        <form className="row saved-page__create" onSubmit={onCreate}>
          <label className="field">
            <span className="field__label">New collection</span>
            <input className="input" value={name} maxLength={80} placeholder="e.g. Week 1: triage" onChange={(e) => setName(e.target.value)} />
          </label>
          <Button type="submit" variant="primary" loading={create.isPending}>Create collection</Button>
        </form>
        <InlineError error={create.error} />
        {collections.isPending ? <LoadingState label="Loading collections…" />
          : collections.isError ? <ErrorState error={collections.error} onRetry={() => void collections.refetch()} />
          : collections.data.length === 0 ? (
            <p className="subtle">No collections yet. Create one here, or use “Save for later” on any question.</p>
          ) : (
            <ul className="saved-list">
              {collections.data.map((c) => (
                <li key={c.id} className="card saved-list__item">
                  <Link to={`/saved/collections/${c.id}`} className="saved-list__title">{c.name}</Link>
                  <span className="subtle">
                    {c.items} {c.items === 1 ? "item" : "items"}
                    {" · "}{c.queue_started && c.items > 0 ? `Queue at item ${c.queue_position + 1} of ${c.items}` : "Queue not started"}
                    {" · "}changed {timeAgo(c.updated_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
      </section>

      <section className="stack" aria-labelledby="bookmarks-title">
        <h2 className="section-title" id="bookmarks-title" ref={marksHeading} tabIndex={-1}><Icon name="bookmark" size={16} />Bookmarks</h2>
        {bookmarks.isPending ? <LoadingState label="Loading bookmarks…" />
          : bookmarks.isError ? <ErrorState error={bookmarks.error} onRetry={() => void bookmarks.refetch()} />
          : bookmarks.data.length === 0 ? (
            <EmptyState title="No bookmarks yet" action={<Link className="btn btn--secondary btn--md" to="/problems?view=questions">Browse questions</Link>}>
              Use the bookmark button on a question in the list, or “Bookmark” on its page.
            </EmptyState>
          ) : (
            // A bookmark's key is the same in every account, so the selection belongs to whoever is signed in.
            <BulkBookmarks key={user?.id ?? ""} marks={bookmarks.data} collections={collections.data ?? []} onRemove={removeBookmark} />
          )}
        <p className="visually-hidden" role="status">{marksNote}</p>
        {/* Shown here, not in the row: a removal is optimistic, so the row is gone if it fails and comes back. */}
        <InlineError error={removeMark.error} />
      </section>
    </div>
  );
}

function BookmarkRow({ mark, onRemove, selected, onSelect }: { mark: Bookmark; onRemove: () => void; selected: boolean; onSelect: (on: boolean) => void }) {
  const itemKind = useItemKind();
  return (
    <li className="card saved-list__item saved-list__item--selectable">
      <SelectBox label={`Select: ${mark.title}`} checked={selected} onChange={onSelect} />
      {mark.href /* retired items stay readable */
        ? <Link to={mark.href} state={{ from: "/saved", fromLabel: "Back to Saved" }} className="saved-list__title">{mark.title}</Link>
        : <span className="saved-list__title">{mark.title}</span>}
      <span className="subtle">{itemKind(mark.item_type, mark.track)} · saved {timeAgo(mark.created_at)}</span>
      {!mark.available && (
        <p className="banner banner--warning">
          {mark.unavailable_reason ?? "This item left the library."}{mark.href ? " You can still open it; it isn't used for practice." : ""} Nothing replaced it; remove the bookmark when you're ready.
        </p>
      )}
      <span className="row">
        <Button size="sm" variant="ghost" aria-label={`Remove bookmark: ${mark.title}`} onClick={onRemove}>Remove</Button>
      </span>
    </li>
  );
}

/**
 * Bookmarks with a selection, and "Add to a collection" for the selected ones (docs/BULK_ACTIONS.md).
 * Adding only puts them in the collection: the bookmarks stay, and nothing about your answers changes.
 */
function BulkBookmarks({ marks, collections, onRemove }: {
  marks: Bookmark[];
  collections: { id: string; name: string; items: number }[];
  onRemove: (mark: Bookmark) => void;
}) {
  const qc = useQueryClient();
  const keys = useMemo(() => marks.map(markKey), [marks]);
  const selection = useSelection(keys);
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<{ verb: string; rows: BatchResult[]; titles: Map<string, string> } | null>(null);
  const [lost, setLost] = useState<{ cid: string; marks: Bookmark[] } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const outcomesRef = useRef<HTMLHeadingElement>(null);
  const focusOutcomes = useRef(false);
  useEffect(() => {
    if (!focusOutcomes.current || !results) return;
    focusOutcomes.current = false;
    outcomesRef.current?.focus();
  }, [results]);
  const destination = collections.find((c) => c.id === target);
  const chosen = marks.filter((m) => selection.selected.includes(markKey(m)));
  const tooMany = chosen.length > BATCH_LIMIT;

  async function send(cid: string, these: Bookmark[]) {
    setBusy(true);
    setError(null);
    setLost(null);
    try {
      const out = await api.batchCollection(cid, { add: these.map((m) => ({ item_type: m.item_type, track: m.track, ref_id: m.ref_id })) });
      qc.setQueryData(["me", "collection", cid], out.collection);
      void qc.invalidateQueries({ queryKey: ["me", "collections"] });
      void qc.invalidateQueries({ queryKey: ["me", "explore"] });
      const name = collections.find((c) => c.id === cid)?.name ?? "the collection";
      setResults({ verb: `adding to “${name}”`, rows: out.results, titles: new Map(these.map((m) => [markKey(m), m.title])) });
      // Done ones leave the selection; the ones that need attention stay picked.
      selection.keep(out.results.filter((r) => !isDone(r)).map((r) => r.key));
      focusOutcomes.current = true; // after the results are on screen (the effect below)
    } catch (e) {
      if (e instanceof ApiError && (e.code === "network_error" || e.status >= 500)) setLost({ cid, marks: these });
      else setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="bulk-bar" role="group" aria-label="Selected bookmarks">
        <label className="checkbox">
          <input type="checkbox" checked={selection.all} onChange={(e) => selection.setAll(e.target.checked)} />
          Select all shown ({marks.length})
        </label>
        <span className="subtle" aria-live="polite">{selection.selected.length} of {marks.length} selected</span>
        {selection.selected.length > 0 && (
          <span className="bulk-bar__action">
            <label className="field bulk-bar__target">
              <span className="field__label">Add the selected to</span>
              <select className="select" value={target} onChange={(e) => setTarget(e.target.value)}>
                <option value="">Choose a collection…</option>
                {collections.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.items})</option>)}
              </select>
            </label>
            <Button size="sm" variant="primary" loading={busy} disabled={!destination || tooMany}
              onClick={() => destination && void send(destination.id, chosen)}>
              {destination ? `Add ${chosen.length} to “${destination.name}”` : "Add"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => selection.setAll(false)}>Clear selection</Button>
          </span>
        )}
      </div>
      {tooMany && <p className="subtle" role="status">Up to {BATCH_LIMIT} at a time: {chosen.length} are selected.</p>}
      {collections.length === 0 && selection.selected.length > 0 && <p className="subtle">Create a collection above first.</p>}
      {lost && <NoReply busy={busy} onRetry={() => void send(lost.cid, lost.marks)} />}
      <InlineError error={error} />
      {results && <BulkOutcomes ref={outcomesRef} results={results.rows} verb={results.verb} titleOf={(k) => results.titles.get(k) ?? k} />}
      <ul className="saved-list">
        {marks.map((b) => (
          <BookmarkRow key={markKey(b)} mark={b} onRemove={() => onRemove(b)}
            selected={selection.isSelected(markKey(b))} onSelect={(on) => selection.toggle(markKey(b), on)} />
        ))}
      </ul>
    </>
  );
}
