import type { ComparisonDoc, ComparisonFigures, Figure } from "@/api/types";

/** A derived figure with its working: the value, the formula, the assumptions; or why it's unknown. */
function FigureLine({ label, f }: { label: string; f: Figure | null }) {
  if (!f) return null;
  return (
    <div className="oc-figure">
      <dt>{label}</dt>
      <dd>
        {f.value !== null
          ? <><span className="oc-amount">{f.formula}</span>{f.assumptions.length > 0 && <span className="subtle"> Assumes {f.assumptions.join("; ")}.</span>}</>
          : <span className="oc-unknown">Unknown: {f.unknown}</span>}
      </dd>
    </div>
  );
}

/** How each number is worked out, per offer, and the optional weighted ordering with every contribution. */
export function Figures({ doc, figures }: { doc: ComparisonDoc; figures: ComparisonFigures }) {
  const label = (id: string) => (doc.offers ?? []).find((o) => o.id === id)?.label ?? id;
  return (
    <section className="card stack-sm" aria-labelledby="oc-figures">
      <h2 className="section-title" id="oc-figures">How the numbers are worked out</h2>
      {figures.currency_note && <p className="banner banner--info">{figures.currency_note}</p>}
      <div className="oc-columns">
        {figures.offers.map((o) => (
          <section key={o.id} className="stack-sm oc-figures-offer" aria-label={`Figures for ${label(o.id)}`}>
            <h3 className="review-minor">{label(o.id)}</h3>
            <dl className="oc-figure-list">
              <FigureLine label="Pay on a yearly basis" f={o.annual_pay} />
              <FigureLine label={`In ${doc.show_in ?? ""}`} f={o.annual_pay_converted} />
              <FigureLine label="Guaranteed first-year cash" f={o.guaranteed_first_year} />
              <FigureLine label={`Guaranteed, in ${doc.show_in ?? ""}`} f={o.guaranteed_first_year_converted} />
              <div className="oc-figure"><dt>Conditional bonus</dt><dd><span className="oc-amount">{o.conditional_bonus.text}</span></dd></div>
              <div className="oc-figure"><dt>Equity</dt><dd>{o.equity}</dd></div>
            </dl>
          </section>
        ))}
      </div>
      <p className="subtle">{figures.not_estimated}</p>
      {figures.weighted && (
        <section className="stack-sm oc-weighted" aria-labelledby="oc-weighted">
          <h3 className="section-title" id="oc-weighted">Your weighted ordering</h3>
          <p><strong>{figures.weighted.label}</strong></p>
          <p className="subtle">{figures.weighted.explanation}</p>
          {figures.weighted.uneven && <p className="banner banner--warning">{figures.weighted.uneven}</p>}
          <ol className="stack-sm">
            {figures.weighted.order.map((id) => {
              const r = figures.weighted!.rows.find((x) => x.id === id)!;
              return (
                <li key={id}>
                  <strong>{r.label}</strong>: {r.total} points from {r.counted} rated factor{r.counted === 1 ? "" : "s"}
                  <ul className="mini-list">
                    {r.contributions.map((c) => <li key={c.factor}>{c.factor}: {c.formula}</li>)}
                    {r.not_counted.map((n) => <li key={n.factor} className="subtle">{n.factor}: not counted ({n.reason})</li>)}
                  </ul>
                </li>
              );
            })}
          </ol>
        </section>
      )}
    </section>
  );
}
