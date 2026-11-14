import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useOfferComparisons } from "@/api/queries";
import type { OfferComparisonSummary } from "@/api/types";
import { Button } from "@/components/Button";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { formatDateTime } from "@/lib/format";

/**
 * /offers/compare: private comparisons of offers whose terms you enter by hand (Volume 10, prompt 9).
 * Active and Archived are two views of the same comparisons (Volume 11, prompt 4; docs/ARCHIVE.md):
 * archiving takes one out of the active list and changes nothing else; Restore brings it back as it
 * was. Deleting is separate (on the comparison's own page) and can't be undone.
 */
export function OfferCompareList() {
  const [params, setParams] = useSearchParams();
  const archived = params.get("archived") === "1";
  const active = useOfferComparisons(false);
  const shelved = useOfferComparisons(true);
  const list = archived ? shelved : active;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [busy, setBusy] = useState<"new" | "example" | null>(null);
  const [moving, setMoving] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [said, setSaid] = useState<{ text: string; to: "active" | "archived" } | null>(null);
  const focusNext = useRef<string | null>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const target = focusNext.current;
    if (!target || list.isFetching) return;
    focusNext.current = null;
    const el = target === "heading" ? headingRef.current : listRef.current?.querySelector<HTMLElement>(`[data-focus="${target}"]`);
    (el ?? headingRef.current)?.focus();
  });

  async function start(example: boolean) {
    setBusy(example ? "example" : "new");
    setError(null);
    try {
      const c = await api.createOfferComparison(example ? { example: true } : { title: "My offers" });
      navigate(`/offers/compare/${c.id}`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  async function move(c: OfferComparisonSummary, toArchive: boolean, rows: OfferComparisonSummary[]) {
    setMoving(c.id);
    setError(null);
    setSaid(null);
    try {
      await api.archiveOfferComparison(c.id, toArchive);
      const at = rows.findIndex((r) => r.id === c.id);
      const neighbour = rows[at + 1] ?? rows[at - 1];
      // Both lists are read again before anything is said, so the counts and the message agree.
      await qc.invalidateQueries({ queryKey: ["me", "offer-comparisons"] });
      void qc.invalidateQueries({ queryKey: ["me", "recent-work"] });
      focusNext.current = neighbour ? `move:${neighbour.id}` : "heading";
      setSaid(toArchive
        ? { text: `"${c.title}" archived. It's under Archived; nothing was deleted.`, to: "archived" }
        : { text: `"${c.title}" restored to your active comparisons, unchanged.`, to: "active" });
    } catch (e) {
      setError(e);
    } finally {
      setMoving(null);
    }
  }

  const show = (which: "active" | "archived") => {
    setSaid(null);
    setParams(which === "archived" ? { archived: "1" } : {}, { replace: true });
  };
  const count = (q: typeof active) => (q.data ? ` (${q.data.length})` : "");

  return (
    <div className="page oc-list">
      <div className="page__header">
        <div>
          <p className="eyebrow">COMPARE OFFERS · PRIVATE</p>
          <h1 className="page__title">Compare offers side by side</h1>
          <p className="page__subtitle">
            Enter the terms of two or three offers yourself, with what matters to you. Every figure shows how it's worked out;
            what you don't know stays unknown. It organises facts and your priorities: it doesn't pick an offer for you.
          </p>
        </div>
      </div>
      <p className="banner banner--info" role="note">
        Only you can see these. Nothing is sent anywhere, no application changes, and tax, equity and benefits aren't valued.
        Try the fictional example before entering real terms.
      </p>
      <span className="row">
        <Button variant="primary" loading={busy === "new"} onClick={() => void start(false)}>New comparison</Button>
        <Button variant="secondary" loading={busy === "example"} onClick={() => void start(true)}>Start with a fictional example</Button>
      </span>
      <InlineError error={error} />

      <section className="card stack-sm" aria-labelledby="oc-mine">
        <div className="oc-list__head">
          <h2 className="section-title" id="oc-mine" ref={headingRef} tabIndex={-1}>{archived ? "Archived comparisons" : "Your comparisons"}</h2>
          <div className="oc-list__views" role="group" aria-label="Which comparisons">
            <Button size="sm" variant={archived ? "ghost" : "secondary"} aria-pressed={!archived} onClick={() => show("active")}>Active{count(active)}</Button>
            <Button size="sm" variant={archived ? "secondary" : "ghost"} aria-pressed={archived} onClick={() => show("archived")}>Archived{count(shelved)}</Button>
          </div>
        </div>
        <p className="subtle" role="status">
          {said?.text}{" "}
          {said && said.to !== (archived ? "archived" : "active") && (
            <Button size="sm" variant="ghost" onClick={() => show(said.to)}>{said.to === "archived" ? "Show archived" : "Show active"}</Button>
          )}
        </p>
        {archived && <p className="subtle">Archived comparisons are kept as they were, links included. Restore puts one back in your active list; deleting is on its own page and can't be undone.</p>}
        {list.isPending ? <LoadingState label="Loading your comparisons…" />
          : list.isError ? <ErrorState error={list.error} onRetry={() => void list.refetch()} />
            : list.data.length === 0 ? (
              <p className="subtle">{archived ? "Nothing archived. Comparisons you archive are kept here." : "No active comparisons."}</p>
            ) : (
              <ul className="mini-list oc-list__items" ref={listRef}>
                {list.data.map((c) => (
                  <li key={c.id} className="oc-list__item">
                    <span>
                      <Link to={`/offers/compare/${c.id}`}>{c.title}</Link>
                      <span className="subtle"> · {c.offers} offer{c.offers === 1 ? "" : "s"} · saved {formatDateTime(c.updated_at)}</span>
                    </span>
                    <Button size="sm" variant="ghost" data-focus={`move:${c.id}`} loading={moving === c.id}
                      aria-label={`${archived ? "Restore" : "Archive"}: ${c.title}`} onClick={() => void move(c, !archived, list.data)}>
                      {archived ? "Restore" : "Archive"}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
      </section>
    </div>
  );
}
