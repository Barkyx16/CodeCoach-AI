import { useState } from "react";

import { Button } from "@/components/Button";

export interface BarPoint {
  key: string;
  label: string; // e.g. "Week of 3 Nov"
  value: number | null; // null = no data that week (drawn as a gap, never as zero)
  detail: string; // full sentence for hover, focus and screen readers
}

/**
 * A single-series weekly bar chart: thin bars with rounded data-ends on a recessive grid, a hover
 * and keyboard-focus readout, gaps for weeks without data, and an exact-values table toggle.
 * One series, so no legend: the title names it.
 */
export function WeeklyBars({ title, points, max, unit, emptyText }: {
  title: string; points: BarPoint[]; max: number; unit: string; emptyText: string;
}) {
  const [active, setActive] = useState<BarPoint | null>(null);
  const [asTable, setAsTable] = useState(false);
  const hasData = points.some((p) => p.value !== null && p.value > 0);
  const step = 16;
  const bar = 12;
  const height = 96;
  const width = Math.max(points.length * step, step);
  const top = Math.max(max, 1);

  return (
    <figure className="weekly-bars">
      <figcaption className="weekly-bars__head">
        <span className="section-title">{title}</span>
        <Button size="sm" variant="ghost" onClick={() => setAsTable((v) => !v)} aria-pressed={asTable}>
          {asTable ? "Show chart" : "Show table"}
        </Button>
      </figcaption>
      {!hasData ? <p className="subtle">{emptyText}</p> : asTable ? (
        <table className="data-table">
          <thead><tr><th scope="col">Week</th><th scope="col">{unit}</th></tr></thead>
          <tbody>{points.map((p) => <tr key={p.key}><td>{p.label}</td><td>{p.value === null ? "No data" : p.value}</td></tr>)}</tbody>
        </table>
      ) : (
        <>
          <p className="subtle weekly-bars__readout" aria-live="polite">{active ? active.detail : "Hover or focus a bar for its value."}</p>
          <svg className="weekly-bars__svg" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="group" aria-label={`${title}. Use "Show table" for exact values.`}>
            <line x1={0} x2={width} y1={height - 0.5} y2={height - 0.5} className="weekly-bars__axis" />
            <line x1={0} x2={width} y1={height / 2} y2={height / 2} className="weekly-bars__grid" />
            {points.map((p, i) => {
              const x = i * step + (step - bar) / 2;
              if (p.value === null) {
                return <rect key={p.key} x={x} y={height - 2} width={bar} height={2} className="weekly-bars__gap" tabIndex={0} role="img" aria-label={p.detail}
                  onMouseEnter={() => setActive(p)} onFocus={() => setActive(p)} onMouseLeave={() => setActive(null)} onBlur={() => setActive(null)} />;
              }
              const h = Math.max(2, (p.value / top) * (height - 4));
              const y = height - h;
              const r = Math.min(4, h / 2, bar / 2);
              const d = `M${x},${height} V${y + r} Q${x},${y} ${x + r},${y} H${x + bar - r} Q${x + bar},${y} ${x + bar},${y + r} V${height} Z`;
              return (
                <g key={p.key} tabIndex={0} role="img" aria-label={p.detail} className="weekly-bars__hit"
                  onMouseEnter={() => setActive(p)} onFocus={() => setActive(p)} onMouseLeave={() => setActive(null)} onBlur={() => setActive(null)}>
                  <rect x={i * step} y={0} width={step} height={height} fill="transparent" />
                  <path d={d} className={`weekly-bars__bar${active?.key === p.key ? " is-active" : ""}`} />
                </g>
              );
            })}
          </svg>
          <div className="weekly-bars__labels subtle" aria-hidden="true">
            <span>{points[0]?.label}</span><span>{points.at(-1)?.label}</span>
          </div>
        </>
      )}
    </figure>
  );
}
