import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { useCollection, useCollections } from "@/api/queries";
import type { Collection, CollectionItem } from "@/api/types";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";

import { transferWords } from "./transfer";

/**
 * Copy or move the chosen items to another collection (Volume 17, prompt 6; docs/BULK_ACTIONS.md,
 * "Copy or move items"). Once the other collection is chosen, the form says what it already has and
 * its room, what arrives with each item, and for a move what leaves this collection and what its queue
 * will skip, before anything is sent.
 */
export function TransferForm({ source, chosen, move, busy, onSend, onCancel }: {
  source: Collection;
  chosen: CollectionItem[];
  move: boolean;
  busy: boolean;
  onSend(to: Collection): void;
  onCancel(): void;
}) {
  const all = useCollections();
  const others = (all.data ?? []).filter((o) => o.id !== source.id);
  const [to, setTo] = useState("");
  const dest = useCollection(to, Boolean(to));
  const ready = to && dest.data?.id === to ? dest.data : null;
  const verb = move ? "Move" : "Copy";
  const n = chosen.length;
  const words = ready ? transferWords({ source, chosen, dest: ready, move }) : [];

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (ready) onSend(ready);
  }

  return (
    <form className="banner banner--info stack-sm" aria-labelledby="transfer-title" onSubmit={onSubmit}
      onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); onCancel(); } }}>
      <strong id="transfer-title">{verb} {n} {n === 1 ? "item" : "items"} to another collection</strong>
      {all.isError ? <InlineError error={all.error} /> : all.isPending ? (
        <p className="subtle" role="status">Loading your collections…</p>
      ) : others.length === 0 ? (
        <p>You have no other collection yet. <Link to="/saved">Make one on Saved</Link>, then come back to {move ? "move" : "copy"} these.</p>
      ) : (
        <label className="field">
          <span className="field__label">To collection</span>
          <select className="select" value={to} autoFocus onChange={(e) => setTo(e.target.value)}>
            <option value="">Choose a collection</option>
            {others.map((o) => <option key={o.id} value={o.id}>{o.name} ({o.items} {o.items === 1 ? "item" : "items"})</option>)}
          </select>
        </label>
      )}
      {to && dest.isPending && <p className="subtle" role="status">Checking what it already has…</p>}
      {to && dest.isError && <InlineError error={dest.error} />}
      {ready && (
        <ul className="transfer-words" aria-label={`Before you ${move ? "move" : "copy"} them`}>
          {words.map((w) => <li key={w}>{w}</li>)}
        </ul>
      )}
      <span className="row">
        <Button type="submit" size="sm" variant="primary" loading={busy} disabled={!ready}>
          {ready ? `${verb} ${n} to “${ready.name}”` : `${verb} ${n}`}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
      </span>
    </form>
  );
}
