import { forwardRef } from "react";

import type { BatchResult } from "@/api/types";
import { Button } from "@/components/Button";

import { isDone, outcomeLabel } from "./bulkSelection";

/**
 * Picking several saved items at once and saying exactly what happened to each (Volume 11,
 * prompt 5; docs/BULK_ACTIONS.md).
 *
 * The selection is a set of stable keys from the rows on screen. It never reaches past them: there's
 * no paging here, "Select all shown" means exactly the rows listed, and a key whose row goes away
 * (removed elsewhere, or by this action) stops counting, so an old selection can't turn into
 * different records. A batch holds at most BATCH_LIMIT items, the server's limit.
 */

/** What happened to each item, said item by item, with the ones that need attention first. */
export const BulkOutcomes = forwardRef<HTMLHeadingElement, {
  results: BatchResult[];
  titleOf: (key: string) => string;
  verb: string;
  /** The heading level that fits where it's shown (the page's outline mustn't skip a level). */
  level?: 2 | 3;
}>(function BulkOutcomes({ results, titleOf, verb, level = 3 }, ref) {
  const Heading = level === 2 ? "h2" : "h3";
  const counts = new Map<string, number>();
  for (const r of results) counts.set(outcomeLabel(r), (counts.get(outcomeLabel(r)) ?? 0) + 1);
  const summary = [...counts].map(([label, n]) => `${n} ${label.toLowerCase()}`).join(", ");
  const attention = results.filter((r) => !isDone(r));
  const ordered = [...attention, ...results.filter(isDone)];
  return (
    <section className="card stack-sm bulk-outcomes" aria-labelledby="bulk-outcomes-title">
      <Heading className="section-title" id="bulk-outcomes-title" ref={ref} tabIndex={-1}>What happened: {verb}</Heading>
      <p role="status">{summary}.{attention.length ? ` ${attention.length} need${attention.length === 1 ? "s" : ""} attention; the rest are done.` : " Nothing needs attention."}</p>
      <ul className="bulk-outcomes__list">
        {ordered.map((r) => (
          <li key={r.key} className={isDone(r) ? "" : "bulk-outcomes__attention"}>
            <strong>{outcomeLabel(r)}</strong>: {titleOf(r.key)} <span className="subtle">({r.message})</span>
          </li>
        ))}
      </ul>
    </section>
  );
});

/** A batch whose reply never came: what it means, and sending the same batch again (safe). */
export function NoReply({ onRetry, busy }: { onRetry: () => void; busy: boolean }) {
  return (
    <div className="banner banner--warning stack-sm" role="alert">
      <p>No reply came, so it isn't known which of these went through. Sending the same ones again is safe: anything already done will say so, and nothing is done twice.</p>
      <span className="row"><Button size="sm" loading={busy} onClick={onRetry}>Send again</Button></span>
    </div>
  );
}

/** The selection checkbox for one row. */
export function SelectBox({ label, checked, onChange }: { label: string; checked: boolean; onChange: (on: boolean) => void }) {
  return (
    <label className="bulk-select">
      <input type="checkbox" checked={checked} aria-label={label} onChange={(e) => onChange(e.target.checked)} />
    </label>
  );
}
