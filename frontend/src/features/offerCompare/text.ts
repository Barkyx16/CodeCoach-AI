import type { ComparisonDoc, ComparisonFigures } from "@/api/types";

/** The comparison as plain text, exactly what "Copy as text" copies. */
export function asText(doc: ComparisonDoc, figures: ComparisonFigures): string {
  const lines = [doc.title, ""];
  for (const o of doc.offers ?? []) {
    const f = figures.offers.find((x) => x.id === o.id);
    lines.push(o.label);
    if (o.source_note) lines.push(`  Source: ${o.source_note}${o.terms_as_of ? ` (terms as of ${o.terms_as_of})` : ""}`);
    if (f) {
      lines.push(`  Pay on a yearly basis: ${f.annual_pay.value !== null ? f.annual_pay.formula : `unknown (${f.annual_pay.unknown})`}`);
      lines.push(`  Guaranteed first-year cash: ${f.guaranteed_first_year.value !== null ? f.guaranteed_first_year.formula : "unknown"}`);
      lines.push(`  Conditional bonus: ${f.conditional_bonus.text}`);
      lines.push(`  Equity: ${f.equity}${o.equity_note ? ` (${o.equity_note})` : ""}`);
    }
    if (o.benefits_note) lines.push(`  Benefits: ${o.benefits_note}`);
    for (const factor of doc.factors ?? []) {
      const r = factor.ratings?.[o.id];
      const said = !r || r.state === "unknown" ? "unknown" : r.state === "not_comparable" ? "not comparable" : `${r.value} of 5 (my rating)`;
      lines.push(`  ${factor.label}: ${said}${r?.note ? `, ${r.note}` : ""}`);
    }
    lines.push("");
  }
  lines.push(figures.not_estimated);
  if (figures.weighted) lines.push(figures.weighted.label);
  return lines.join("\n");
}
