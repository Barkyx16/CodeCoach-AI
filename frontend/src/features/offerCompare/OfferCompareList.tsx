import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useOfferComparisons } from "@/api/queries";
import { Button } from "@/components/Button";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { formatDateTime } from "@/lib/format";

/** /offers/compare: private comparisons of offers whose terms you enter by hand (Volume 10, prompt 9). */
export function OfferCompareList() {
  const list = useOfferComparisons();
  const navigate = useNavigate();
  const [busy, setBusy] = useState<"new" | "example" | null>(null);
  const [error, setError] = useState<unknown>(null);
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
      {list.isPending ? <LoadingState label="Loading your comparisons…" />
        : list.isError ? <ErrorState error={list.error} onRetry={() => void list.refetch()} />
          : list.data.length > 0 && (
            <section className="card stack-sm" aria-labelledby="oc-mine">
              <h2 className="section-title" id="oc-mine">Your comparisons</h2>
              <ul className="mini-list">
                {list.data.map((c) => (
                  <li key={c.id}><Link to={`/offers/compare/${c.id}`}>{c.title}</Link><span className="subtle"> · {c.offers} offer{c.offers === 1 ? "" : "s"} · saved {formatDateTime(c.updated_at)}</span></li>
                ))}
              </ul>
            </section>
          )}
    </div>
  );
}
