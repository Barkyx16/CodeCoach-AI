import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useCollection, useCollectionMutation, useCollections, useDeleteCollection, useLimit } from "@/api/queries";
import type { Collection, CollectionItem, RequestOutcome } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";
import { useAuth } from "@/auth/useAuth";
import { EarlierActionNotice } from "@/features/recovery/EarlierActionNotice";
import { useEarlierAction } from "@/features/recovery/useEarlierAction";
import { fingerprint, forgetIntent, keyForIntent } from "@/lib/pendingIntents";
import { useRequestKey } from "@/lib/requestKey";

import { BulkOutcomes, NoReply, SelectBox } from "./bulk";
import { type BulkResult, isDone, useSelection } from "./bulkSelection";
import { TransferForm } from "./CollectionTransfer";
import { useItemKind } from "./labels";
import { SavedFreshness } from "./SavedFreshness";
import { itemKey } from "./transfer";

/** A copy or move whose reply never came: the same items again, named by what they are (the page may
 * have reloaded without them since). */
type LostTransfer = { kind: "transfer"; to: Collection; move: boolean; chosen: CollectionItem[] };

/** One collection: rename, reorder (buttons, keyboard-friendly), remove items, start the practice queue. */
export function CollectionPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const made = (useLocation().state as { copied?: string } | null)?.copied;
  const collection = useCollection(id);
  const rename = useCollectionMutation((name: string) => api.renameCollection(id, name));
  const reorder = useCollectionMutation((ids: string[]) => api.reorderCollection(id, ids));
  const remove = useCollectionMutation((itemId: string) => api.removeFromCollection(id, itemId));
  const reviewItem = useCollectionMutation(({ itemId, version }: { itemId: string; version: number }) => api.reviewCollectionItem(id, itemId, version));
  const start = useCollectionMutation((position: number) => api.setQueuePosition(id, position));
  const destroy = useDeleteCollection();
  // Duplicate (Volume 16, prompt 8): one key per exact request, so a retry after a lost reply makes one copy.
  const all = useCollections();
  // The server's limit, as it serves it (Volume 17, prompt 7): unread, the form states no number.
  const maxCollections = useLimit("collections_per_account");
  const copies = useQueryClient();
  const requestKey = useRequestKey();
  // One key per copy or move (Volume 18, prompt 5): sent again after a lost reply, the server gives back
  // what the first request did. Kept on this device before sending (Volume 19, prompt 1), so after a
  // reload the page asks what that key made instead of losing it; in memory only if this browser can't
  // keep it.
  const transferKey = useRequestKey();
  const { user } = useAuth();
  const earlierTransfer = useEarlierAction("transfer", id || null);
  const otherId = earlierTransfer.status === "found" ? earlierTransfer.outcome.transfer?.destination_id ?? "" : "";
  const otherCollection = useCollection(otherId, !!otherId);
  const [duplicating, setDuplicating] = useState(false);
  const [copyName, setCopyName] = useState("");
  const [copyLost, setCopyLost] = useState(false);
  const duplicate = useMutation({
    mutationFn: (name: string) => api.duplicateCollection(id, { name: name || null, client_request_id: requestKey.keyFor({ id, name }) }),
    onSuccess: (copy) => {
      requestKey.done();
      copies.setQueryData(["me", "collection", copy.id], copy);
      void copies.invalidateQueries({ queryKey: ["me", "collections"] });
      setDuplicating(false);
      setCopyLost(false);
      navigate(`/saved/collections/${copy.id}`, { state: { copied: copy.name } });
    },
    onError: (e) => setCopyLost(e instanceof ApiError && (e.code === "network_error" || e.status >= 500)),
  });
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
  const perBatch = useLimit("items_per_batch"); // the server's limit on one request
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkResults, setBulkResults] = useState<{ verb: string; rows: BulkResult[]; titles: Map<string, string> } | null>(null);
  const [bulkLost, setBulkLost] = useState<{ kind: "remove" | "review"; ids: string[] } | LostTransfer | null>(null);
  // Copy or move the chosen items to another collection (Volume 17, prompt 6).
  const [transferring, setTransferring] = useState<"copy" | "move" | null>(null);
  const [transferred, setTransferred] = useState<{ to: Collection; move: boolean; resent: boolean; replayed: boolean } | null>(null);
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
  const tooMany = perBatch !== undefined && selection.selected.length > perBatch;

  async function removeSelected(ids: string[]) {
    setBulkBusy(true);
    setBulkError(null);
    setBulkLost(null);
    setTransferred(null);
    const titles = new Map(items.filter((i) => ids.includes(i.id)).map((i) => [i.id, i.title]));
    try {
      const out = await api.batchCollection(id, { remove: ids });
      qc.setQueryData(["me", "collection", id], out.collection);
      void qc.invalidateQueries({ queryKey: ["me", "collections"] });
      void qc.invalidateQueries({ queryKey: ["me", "explore"] });
      setBulkResults({ verb: `removing from “${c.name}”`, rows: out.results, titles: new Map([...(bulkResults?.titles ?? []), ...titles]) });
      selection.keep(out.results.filter((r) => !isDone(r)).map((r) => r.key));
      focusOutcomes.current = true; // after the results are on screen (the effect below)
    } catch (e) {
      if (e instanceof ApiError && (e.code === "network_error" || e.status >= 500)) setBulkLost({ kind: "remove", ids });
      else setBulkError(e);
    } finally {
      setBulkBusy(false);
    }
  }

  // "Mark reviewed" for several, each at the version its row shows: the same rule as one at a time,
  // and the items stay where they are.
  async function reviewSelected(ids: string[]) {
    setBulkBusy(true);
    setBulkError(null);
    setBulkLost(null);
    setTransferred(null);
    const chosen = items.filter((i) => ids.includes(i.id));
    try {
      const out = await api.reviewCollectionItems(id, chosen.map((i) => ({ itemId: i.id, reviewedVersion: i.freshness?.current_version ?? 1 })));
      qc.setQueryData(["me", "collection", id], out.collection);
      setBulkResults({ verb: `marking reviewed in “${c.name}”`, rows: out.results, titles: new Map(chosen.map((i) => [i.id, i.title])) });
      selection.keep(out.results.filter((r) => !isDone(r)).map((r) => r.key));
      focusOutcomes.current = true;
    } catch (e) {
      if (e instanceof ApiError && (e.code === "network_error" || e.status >= 500)) setBulkLost({ kind: "review", ids });
      else setBulkError(e);
    } finally {
      setBulkBusy(false);
    }
  }

  // Each item goes as it was (its version, when it was added, its "Mark reviewed"); a move takes it out
  // of here only once it's in the other collection. Sent again after a lost reply, nothing changes twice:
  // an item the first request already copied or moved reads "Already there".
  async function transferSelected(chosen: CollectionItem[], to: Collection, moving: boolean, resent = false) {
    setBulkBusy(true);
    setBulkError(null);
    setBulkLost(null);
    try {
      const items = chosen.map((i) => ({ item_type: i.item_type, track: i.track, ref_id: i.ref_id }));
      const intent = user ? keyForIntent(user.id, "transfer", id, fingerprint(to.id, moving ? "move" : "copy", JSON.stringify(items))) : null;
      const key = intent?.kept ? intent.key : transferKey.keyFor({ id, to: to.id, move: moving, items });
      const out = await api.transferCollectionItems(id, { to: to.id, move: moving, items, client_request_id: key });
      transferKey.done();
      forgetIntent(user?.id, "transfer", id, key);
      qc.setQueryData(["me", "collection", id], out.source);
      qc.setQueryData(["me", "collection", to.id], out.destination);
      void qc.invalidateQueries({ queryKey: ["me", "collections"] });
      void qc.invalidateQueries({ queryKey: ["me", "explore"] });
      setBulkResults({ verb: `${moving ? "moving" : "copying"} to “${out.destination.name}”`, rows: out.results, titles: new Map(chosen.map((i) => [itemKey(i), i.title])) });
      setTransferred({ to: out.destination, move: moving, resent, replayed: Boolean(out.replayed) });
      const open = new Set(out.results.filter((r) => !isDone(r)).map((r) => r.key));
      selection.keep(chosen.filter((i) => open.has(itemKey(i))).map((i) => i.id));
      setTransferring(null);
      focusOutcomes.current = true;
    } catch (e) {
      if (e instanceof ApiError && (e.code === "network_error" || e.status >= 500)) setBulkLost({ kind: "transfer", to, move: moving, chosen });
      else {
        forgetIntent(user?.id, "transfer", id); // refused: nothing to ask about after a reload
        setBulkError(e);
      }
    } finally {
      setBulkBusy(false);
    }
  }

  function retryLost() {
    if (!bulkLost) return;
    if (bulkLost.kind === "transfer") void transferSelected(bulkLost.chosen, bulkLost.to, bulkLost.move, true);
    else if (bulkLost.kind === "remove") void removeSelected(bulkLost.ids);
    else void reviewSelected(bulkLost.ids);
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

  const count = all.data?.length;
  const atLimit = count !== undefined && maxCollections !== undefined && count >= maxCollections;
  const original = c.copied_from_id ? all.data?.find((x) => x.id === c.copied_from_id) : undefined;

  function onDuplicate(e: FormEvent) {
    e.preventDefault();
    if (!atLimit) duplicate.mutate(copyName.trim());
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
          <Button size="sm" variant="ghost" id="duplicate-collection" aria-expanded={duplicating} onClick={() => setDuplicating((v) => !v)}>Duplicate</Button>
          <Button size="sm" variant="ghost" id="delete-collection" aria-expanded={confirming} onClick={() => setConfirming(true)}>Delete</Button>
          {items.length > 0 && (
            <Button variant="primary" loading={start.isPending} onClick={() => void onStart()}>
              {c.queue_started ? "Continue practice" : "Start this collection"}
            </Button>
          )}
        </div>
      </div>
      <InlineError error={start.error} />
      {made && made === c.name && <p className="banner banner--success" role="status">Made “{made}”: the same items in the same order, its queue at the beginning.</p>}
      {c.copied_from_id && (
        <p className="subtle">
          A copy of {original ? <Link to={`/saved/collections/${original.id}`}>“{original.name}”</Link> : "a collection you've since deleted"}.
          {" "}Its queue and its “Mark reviewed” are its own: nothing you do here changes the other.
        </p>
      )}

      {duplicating && (
        <form className="banner banner--info stack-sm" aria-labelledby="duplicate-title" onSubmit={onDuplicate}
          onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); setDuplicating(false); document.getElementById("duplicate-collection")?.focus(); } }}>
          <strong id="duplicate-title">Duplicate “{c.name}”</strong>
          <p>The copy has the same {c.items === 1 ? "item" : `${c.items} items`} in the same order, each at the version it was added at and with its “Mark reviewed”. Its queue starts at the beginning, and this collection doesn't change. Your saved items aren't touched.</p>
          {count !== undefined && maxCollections !== undefined && (atLimit
            ? <p className="banner banner--warning" role="status">You have {count} of {maxCollections} collections: delete one to make room for a copy.</p>
            : count >= maxCollections - 5 && <p className="subtle">You have {count} of {maxCollections} collections; the copy would make {count + 1}.</p>)}
          <label className="field">
            <span className="field__label">Name for the copy</span>
            <input className="input" value={copyName} maxLength={80} placeholder={`${c.name} (copy)`} autoFocus onChange={(e) => setCopyName(e.target.value)} />
          </label>
          <p className="subtle">Leave it empty for “{c.name} (copy)”, numbered if you already have one. A name you already use, in any letter case, isn't taken twice.</p>
          <span className="row">
            <Button type="submit" size="sm" variant="primary" loading={duplicate.isPending} disabled={atLimit}>Make the copy</Button>
            <Button size="sm" variant="ghost" onClick={() => setDuplicating(false)}>Cancel</Button>
          </span>
          {copyLost ? (
            <div className="banner banner--warning stack-sm" role="alert">
              <p>No reply came, so it isn't known whether the copy was made. Sending it again is safe: it makes one copy, not two.</p>
              <span className="row"><Button size="sm" loading={duplicate.isPending} onClick={() => duplicate.mutate(copyName.trim())}>Send again</Button></span>
            </div>
          ) : <InlineError error={duplicate.error} />}
        </form>
      )}

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
      {/* A copy or move sent before the page reloaded, whose reply never came (Volume 19, prompt 1): what
          its key made, read from the server, never sent again. */}
      <EarlierActionNotice earlier={earlierTransfer} noun="copy or move"
        found={earlierTransfer.status === "found" ? "These are what it did, and nothing was done twice." : null} />
      {earlierTransfer.status === "found" && earlierTransfer.outcome.transfer && (
        <EarlierTransfer made={earlierTransfer.outcome.transfer} other={otherCollection.data ?? null}
          titleOf={(k) => [...items, ...(otherCollection.data?.item_list ?? [])].find((i) => itemKey(i) === k)?.title ?? "An item"} />
      )}
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
              <Button size="sm" loading={bulkBusy} disabled={tooMany} onClick={() => void removeSelected(selection.selected)}>
                Remove {selection.selected.length} from “{c.name}”
              </Button>
              <Button size="sm" loading={bulkBusy} disabled={tooMany} onClick={() => void reviewSelected(selection.selected)}>
                Mark {selection.selected.length} reviewed
              </Button>
              <Button size="sm" variant="secondary" disabled={tooMany} aria-expanded={transferring === "copy"} onClick={() => setTransferring("copy")}>
                Copy {selection.selected.length} to…
              </Button>
              <Button size="sm" variant="secondary" disabled={tooMany} aria-expanded={transferring === "move"} onClick={() => setTransferring("move")}>
                Move {selection.selected.length} to…
              </Button>
              <Button size="sm" variant="ghost" onClick={() => selection.setAll(false)}>Clear selection</Button>
            </span>
          )}
        </div>
        {tooMany && <p className="subtle" role="status">Up to {perBatch} at a time: {selection.selected.length} are selected.</p>}
        {selection.selected.length > 0 && (
          <p className="subtle">Removing only takes them out of this collection. The questions stay in the library, and your bookmarks and answers aren't touched.</p>
        )}
        {transferring && selection.selected.length > 0 && !tooMany && (
          <TransferForm key={transferring} source={c} move={transferring === "move"} busy={bulkBusy}
            chosen={items.filter((i) => selection.isSelected(i.id))}
            onSend={(to) => void transferSelected(items.filter((i) => selection.isSelected(i.id)), to, transferring === "move")}
            onCancel={() => setTransferring(null)} />
        )}
        {bulkLost && <NoReply busy={bulkBusy} onRetry={retryLost} />}
        <InlineError error={bulkError} />
        {bulkResults && <BulkOutcomes ref={outcomesRef} level={2} results={bulkResults.rows} verb={bulkResults.verb} titleOf={(k) => bulkResults.titles.get(k) ?? "An item"} />}
        {transferred && <TransferredLinks source={c} {...transferred} />}
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
                <SavedFreshness title={item.title} freshness={item.freshness}
                  review={(version) => reviewItem.mutateAsync({ itemId: item.id, version })} />
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
      {items.length === 0 && bulkResults && <BulkOutcomes ref={outcomesRef} level={2} results={bulkResults.rows} verb={bulkResults.verb} titleOf={(k) => bulkResults.titles.get(k) ?? "An item"} />}
      {items.length === 0 && transferred && <TransferredLinks source={c} {...transferred} />}
      {items.length === 0 && bulkLost && <NoReply busy={bulkBusy} onRetry={retryLost} />}
      <InlineError error={reorder.error ?? remove.error} />
    </div>
  );
}

/** After a copy or move: both collections, as they now are. */
/** What an earlier copy or move did, as its first reply said: the same outcomes, and the other collection. */
function EarlierTransfer({ made, other, titleOf }: {
  made: NonNullable<RequestOutcome["transfer"]>; other: Collection | null; titleOf: (key: string) => string;
}) {
  const verb = made.move === false ? "copying" : made.move ? "moving" : "copying or moving";
  return (
    <div className="stack-sm">
      <BulkOutcomes level={2} results={made.results} titleOf={titleOf}
        verb={other ? `${verb} to “${other.name}”` : verb} />
      {other && <p><Link to={`/saved/collections/${other.id}`}>Open “{other.name}”</Link></p>}
    </div>
  );
}

function TransferredLinks({ source, to, move, resent, replayed }: { source: Collection; to: Collection; move: boolean; resent: boolean; replayed: boolean }) {
  const count = (c: Collection) => `${c.items} ${c.items === 1 ? "item" : "items"}`;
  return (
    <p className="subtle transfer-links">
      Now: <Link to={`/saved/collections/${to.id}`}>“{to.name}”</Link> has {count(to)}, and{" "}
      <Link to={`/saved/collections/${source.id}`} aria-current="page">“{source.name}”</Link> has {count(source)}
      {move ? "." : " (unchanged)."}
      {resent && (replayed
        ? " This was sent again after no reply came: these are what the first request did, and nothing was done twice."
        : " This was sent again after no reply came: an item the first request already did reads “Already there”.")}
    </p>
  );
}
