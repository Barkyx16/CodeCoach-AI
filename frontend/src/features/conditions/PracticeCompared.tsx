import type { PracticeComparison } from "@/api/types";
import { formatDateTime } from "@/lib/format";

/**
 * A drill, whiteboard design or work sample beside the previous assessed attempt at the same item, by
 * the one comparison contract (docs/COMPARING_ATTEMPTS.md, "Drills, whiteboards and work samples").
 * Both results are shown as they were given; the explanation says whether they compare and why.
 * Nothing here says one improved on the other.
 */
export function PracticeCompared({ compared }: { compared: PracticeComparison }) {
  const prev = compared.previous;
  return (
    <section className="submission-compared stack-sm" aria-label="Compared with your previous attempt">
      <h3 className="section-title">Compared with your previous attempt</h3>
      <ul className="mini-list">
        <li>
          <span className="submission-compared__when">Earlier, <time dateTime={prev.created_at}>{formatDateTime(prev.created_at)}</time>:</span>{" "}
          {prev.result}
        </li>
        <li><span className="submission-compared__when">This one:</span> {compared.result}</li>
      </ul>
      <p className="subtle">{compared.comparison.explanation}</p>
    </section>
  );
}
