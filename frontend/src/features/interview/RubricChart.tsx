import type { RubricScore } from "@/api/types";

import { DIMENSION_LABELS, SCORE_WORDS } from "./phases";

/**
 * Single-series horizontal bars on a fixed 1–4 scale. One hue and no legend (the title names
 * the series). The score is printed beside each bar, and the evidence is shown under it, so
 * nothing depends on reading the bar length or color alone.
 */
export function RubricChart({ scores }: { scores: RubricScore[] }) {
  return (
    <ul className="rubric" aria-label="Rubric scores, out of 4">
      {scores.map((s) => (
        <li key={s.dimension} className="rubric__row">
          <div className="rubric__head">
            <span className="rubric__label">{DIMENSION_LABELS[s.dimension] ?? s.dimension}</span>
            <span className="rubric__bar" role="img" aria-label={`${s.score} out of 4`}>
              <span className="rubric__fill" style={{ width: `${(s.score / 4) * 100}%` }} />
            </span>
            <span className="rubric__value">{s.score}/4 <span className="subtle">{SCORE_WORDS[s.score]}</span></span>
          </div>
          <p className="rubric__evidence subtle">{s.evidence}</p>
        </li>
      ))}
    </ul>
  );
}
