import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useCollections, useIsBookmarked, useToggleBookmark } from "@/api/queries";
import type { SavedItemRef } from "@/api/types";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { InlineError } from "@/components/States";

const NEW = "__new";

/** Bookmark this question/problem, or add it to one of your collections (or a new one). */
export function SaveControls({ item, title }: { item: SavedItemRef; title: string }) {
  const qc = useQueryClient();
  const bookmarked = useIsBookmarked(item, true);
  const toggle = useToggleBookmark();
  const collections = useCollections(true, item);
  const [target, setTarget] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<unknown>(null);
  const list = collections.data ?? [];
  const chosen = target || (list.find((c) => !c.contains)?.id ?? NEW);
  const holding = list.filter((c) => c.contains);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage("");
    setBusy(true);
    try {
      const id = chosen === NEW ? (await api.createCollection(name.trim() || "Untitled")).id : chosen;
      const c = await api.addToCollection(id, item);
      qc.setQueryData(["me", "collection", c.id], c);
      setMessage(`Added to “${c.name}”.`);
      setName("");
      setTarget("");
    } catch (err) {
      setError(err); // e.g. 409 "It's already in “Week 1”."
    } finally {
      setBusy(false);
      void qc.invalidateQueries({ queryKey: ["me", "collections"] });
      void qc.invalidateQueries({ queryKey: ["me", "explore"] });
    }
  }

  return (
    <section className="card stack save-controls" aria-labelledby="save-title">
      <h2 className="section-title" id="save-title"><Icon name="bookmark" size={16} />Save for later</h2>
      <Button aria-pressed={Boolean(bookmarked)} disabled={bookmarked === undefined} loading={toggle.isPending}
        onClick={() => toggle.mutate({ ref: item, on: !bookmarked })}>
        {bookmarked ? "Bookmarked" : "Bookmark"}
      </Button>
      {toggle.isError && (
        <p className="banner banner--warning" role="alert">
          Couldn't {toggle.variables?.on ? "bookmark" : "remove the bookmark from"} “{title}”. Nothing was changed.{" "}
          <button type="button" className="link-button" onClick={() => toggle.variables && toggle.mutate(toggle.variables)}>Try again</button>
        </p>
      )}
      <form className="stack-sm" onSubmit={add}>
        {/* With no collections yet there's nothing to choose: just name the new one. */}
        {(collections.isPending || list.length > 0) && (
          <label className="field">
            <span className="field__label">Add to a collection</span>
            <select className="input" value={chosen} onChange={(e) => { setTarget(e.target.value); setMessage(""); setError(null); }}
              disabled={collections.isPending}>
              {list.map((c) => <option key={c.id} value={c.id} disabled={Boolean(c.contains)}>{c.name}{c.contains ? " (already added)" : ""}</option>)}
              <option value={NEW}>New collection…</option>
            </select>
          </label>
        )}
        {chosen === NEW && (
          <label className="field">
            <span className="field__label">New collection name</span>
            <input className="input" value={name} maxLength={80} placeholder="e.g. Night shift prep" onChange={(e) => setName(e.target.value)} />
          </label>
        )}
        <Button type="submit" size="sm" loading={busy}>Add</Button>
      </form>
      <p role="status" className="subtle">{message}</p>
      <InlineError error={error} />
      {holding.length > 0 && (
        <p className="subtle">In: {holding.map((c, i) => <span key={c.id}>{i > 0 && ", "}<Link to={`/saved/collections/${c.id}`}>{c.name}</Link></span>)}</p>
      )}
    </section>
  );
}
