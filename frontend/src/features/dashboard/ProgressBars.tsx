interface Row {
  key: string;
  label: string;
  total: number;
  solved: number;
  attempted?: number;
}

/**
 * Thin segmented bars: solved, then attempted-but-unsolved, on a recessive track. The figures
 * are printed beside each bar (so values never rely on color), and one legend serves the list.
 */
export function ProgressBars({ rows, showAttempted = true, columns = false, unit = "solved" }: {
  rows: Row[]; showAttempted?: boolean; /** Two columns of rows on wide screens (long lists). */ columns?: boolean;
  /** What the filled part counts, for screen readers ("solved" problems, "answered" questions). */ unit?: string;
}) {
  return (
    <div className={columns ? "pbars pbars--columns" : "pbars"}>
      {/* A single series needs no legend: the card title names it. */}
      {showAttempted && (
        <div className="pbars__legend" aria-hidden="true">
          <span><i className="swatch swatch--solved" /> Solved</span>
          <span><i className="swatch swatch--attempted" /> Attempted</span>
        </div>
      )}
      <ul className="pbars__list">
        {rows.map((r) => {
          const pending = showAttempted ? Math.max(0, (r.attempted ?? 0) - r.solved) : 0;
          const solvedPct = r.total ? (r.solved / r.total) * 100 : 0;
          const pendingPct = r.total ? (pending / r.total) * 100 : 0;
          const text = `${r.solved}/${r.total} ${unit}${pending ? `, ${pending} in progress` : ""}`;
          return (
            <li key={r.key} className="pbars__row">
              <span className="pbars__label" title={r.label}>{r.label}</span>
              <span className="pbars__bar" role="img" aria-label={`${r.label}: ${text}`}>
                {solvedPct > 0 && <span className="pbars__seg pbars__seg--solved" style={{ width: `${solvedPct}%` }} />}
                {pendingPct > 0 && <span className="pbars__seg pbars__seg--attempted" style={{ width: `${pendingPct}%` }} />}
              </span>
              <span className="pbars__value">{r.solved}/{r.total}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
