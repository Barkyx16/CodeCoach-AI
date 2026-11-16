import type { Submission, SubmissionComparison } from "@/api/types";
import { StatusBadge } from "@/components/Badge";
import { formatDateTime } from "@/lib/format";

/**
 * A finished submission beside the previous judged one of the same problem and mode, by the one
 * comparison contract (docs/COMPARING_ATTEMPTS.md, "Coding submissions"). Each verdict is shown as
 * the judge gave it; the explanation says whether the two compare and why. Nothing here says one
 * improved on the other.
 */
export function SubmissionCompared({ current, compared }: { current: Submission; compared: SubmissionComparison }) {
  const prev = compared.previous;
  const c = compared.comparison;
  const noun = current.mode === "run" ? "run" : "submission";
  const counts = (passed?: number | null, total?: number | null, hiddenPassed?: number | null, hiddenTotal?: number | null) =>
    passed == null || total == null ? null
      : <span className="subtle"> {passed} of {total} tests passed{hiddenTotal ? ` (hidden ${hiddenPassed ?? 0} of ${hiddenTotal})` : ""}</span>;
  const r = current.result;
  return (
    <section className="submission-compared stack-sm" id="comparison" aria-label={`Compared with your previous ${noun}`}>
      <h3 className="section-title">Compared with your previous {noun}</h3>
      <ul className="mini-list">
        <li>
          <span className="submission-compared__when">Earlier, <time dateTime={prev.created_at}>{formatDateTime(prev.created_at)}</time>:</span>{" "}
          <StatusBadge status={prev.status} />{counts(prev.passed_count, prev.total_count, prev.hidden_passed, prev.hidden_total)}
        </li>
        <li>
          <span className="submission-compared__when">This one:</span>{" "}
          <StatusBadge status={current.status} />{counts(r?.passed_count, r?.total_count, r?.hidden_passed, r?.hidden_total)}
        </li>
      </ul>
      <p className="subtle">{c.explanation}</p>
    </section>
  );
}
