import { useState } from "react";

import type { Progress } from "@/api/types";
import { Button } from "@/components/Button";

import { heatLevel } from "./heatLevel";

type Day = Progress["activity"][number];

const LEVEL_LABELS = ["None", "1–2", "3–5", "6–9", "10+"];

function label(day: Day): string {
  const date = new Date(`${day.day}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  return `${date}: ${day.events} ${day.events === 1 ? "activity" : "activities"}`;
}

export function ActivityHeatmap({ days }: { days: Day[] }) {
  const [hovered, setHovered] = useState<Day | null>(null);
  const [asTable, setAsTable] = useState(false);
  const total = days.reduce((n, d) => n + d.events, 0);

  return (
    <div className="heatmap">
      <div className="heatmap__header">
        <span className="subtle" aria-live="polite">{hovered ? label(hovered) : `${total} ${total === 1 ? "activity" : "activities"} in the last 28 days`}</span>
        <Button size="sm" variant="ghost" onClick={() => setAsTable((v) => !v)} aria-pressed={asTable}>
          {asTable ? "Show chart" : "Show table"}
        </Button>
      </div>
      {asTable ? (
        <table className="data-table">
          <thead><tr><th scope="col">Day</th><th scope="col">Activities</th></tr></thead>
          <tbody>{days.map((d) => <tr key={d.day}><td>{d.day}</td><td>{d.events}</td></tr>)}</tbody>
        </table>
      ) : (
        <>
          <div className="heatmap__grid" role="img" aria-label={`Activity over the last 28 days, ${total} in total. Use "Show table" for exact values.`}
            onMouseLeave={() => setHovered(null)}>
            {days.map((d) => (
              <span key={d.day} className={`heatmap__cell heatmap__cell--${heatLevel(d.events)}`}
                onMouseEnter={() => setHovered(d)} title={label(d)} data-testid="heat-cell" />
            ))}
          </div>
          <div className="heatmap__legend" aria-hidden="true">
            <span className="subtle">Less</span>
            {LEVEL_LABELS.map((l, i) => <span key={l} className={`heatmap__cell heatmap__cell--${i}`} title={l} />)}
            <span className="subtle">More</span>
          </div>
        </>
      )}
    </div>
  );
}
