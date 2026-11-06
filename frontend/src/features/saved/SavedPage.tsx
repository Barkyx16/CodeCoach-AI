import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useBookmarks, useCollectionMutation, useCollections, useToggleBookmark } from "@/api/queries";
import type { Bookmark } from "@/api/types";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";
import { timeAgo } from "@/lib/format";

import { useItemKind } from "./labels";

/** Your bookmarks and private collections. Nothing here is visible to anyone else. */
export function SavedPage() {
  const navigate = useNavigate();
  const collections = useCollections();
  const bookmarks = useBookmarks();
  const create = useCollectionMutation((name: string) => api.createCollection(name));
  const removeMark = useToggleBookmark();
  const marksHeading = useRef<HTMLHeadingElement>(null);
  const [marksNote, setMarksNote] = useState("");

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
            <p className="subtle">No collections yet. Create one here, or use “Add to a collection” on any question.</p>
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
            <ul className="saved-list">{bookmarks.data.map((b) => <BookmarkRow key={`${b.item_type}:${b.track}:${b.ref_id}`} mark={b} onRemove={() => removeBookmark(b)} />)}</ul>
          )}
        <p className="visually-hidden" role="status">{marksNote}</p>
        {/* Shown here, not in the row: a removal is optimistic, so the row is gone if it fails and comes back. */}
        <InlineError error={removeMark.error} />
      </section>
    </div>
  );
}

function BookmarkRow({ mark, onRemove }: { mark: Bookmark; onRemove: () => void }) {
  const itemKind = useItemKind();
  return (
    <li className="card saved-list__item">
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
