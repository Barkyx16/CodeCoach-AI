import type { OfferCard } from "@/api/types";

/** The fictional fact card. Unknown terms say so in words; nothing here is a real offer. */
export function FactCard({ card }: { card: OfferCard }) {
  return (
    <section className="card stack-sm offer-card" aria-labelledby="offer-card-title">
      <h2 className="section-title" id="offer-card-title">The offer (fictional)</h2>
      <p className="subtle">{card.role} at {card.employer}. You're talking to {card.counterpart}.{card.currency ? ` Amounts are in ${card.currency}, before tax.` : ""}</p>
      <dl className="offer-terms">
        {card.terms.map((t) => (
          <div key={t.id} className="offer-term">
            <dt>{t.label}</dt>
            <dd>{t.value ?? <em className="offer-unknown">Not stated in the offer (unknown)</em>}</dd>
          </div>
        ))}
      </dl>
      <p className="subtle">{card.review_status}</p>
    </section>
  );
}
