import { Link } from "react-router-dom";

import { useOfferCases, useOfferRehearsals } from "@/api/queries";
import { Card } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/States";
import { formatDateTime } from "@/lib/format";

const OUTCOME: Record<string, string> = {
  accept: "accepted", decline: "declined", time: "asked for time", counter: "countered", unclear: "no clear answer",
};

/** /offers: rehearse an offer conversation against a fictional fact card (Volume 10, prompt 8). */
export function OfferList() {
  const cases = useOfferCases();
  const mine = useOfferRehearsals();
  return (
    <div className="page offers-list">
      <div className="page__header">
        <div>
          <p className="eyebrow">OFFER CONVERSATIONS</p>
          <h1 className="page__title">Rehearse an offer conversation</h1>
          <p className="page__subtitle">
            Practise three things: asking what an offer leaves unclear, making a request with a reason, and answering a
            counteroffer, including asking for time or saying no. The offer and the other person are made up, and nothing is
            sent to anyone.
          </p>
        </div>
      </div>
      <p className="banner banner--info" role="note">
        This helps you practise how you say it. It can't predict what a real employer would offer or agree to, and it doesn't
        give salary, tax or legal advice.
      </p>
      <p>Weighing real offers? <Link to="/offers/compare">Compare offers privately</Link>, with your own priorities.</p>
      {cases.isPending ? <LoadingState label="Loading cases…" />
        : cases.isError ? <ErrorState error={cases.error} onRetry={() => void cases.refetch()} />
          : (
            <ul className="stack">
              {cases.data.map((c) => (
                <li key={c.id}>
                  <Card className="stack-sm">
                    <h2 className="section-title"><Link to={`/offers/${c.id}`}>{c.title}</Link></h2>
                    <p className="subtle">{c.role} · {c.employer}</p>
                  </Card>
                </li>
              ))}
            </ul>
          )}
      {mine.data && mine.data.length > 0 && (
        <section className="card stack-sm" aria-labelledby="offers-mine">
          <h2 className="section-title" id="offers-mine">Your rehearsals</h2>
          <ul className="mini-list">
            {mine.data.map((r) => (
              <li key={r.id}>
                <Link to={`/offers/rehearsals/${r.id}`}>{r.title}</Link>
                <span className="subtle"> · {formatDateTime(r.created_at)} · {r.status === "in_progress" ? "in progress" : r.outcome ? OUTCOME[r.outcome] ?? r.outcome : "stopped"}{r.parent_id ? " · a different approach" : ""}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
