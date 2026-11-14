import { Link } from "react-router-dom";

import type { ScheduleKind } from "@/api/types";

/** "Add to schedule" for any activity: opens the schedule with it chosen. */
export function ScheduleLink({ kind, refId, title, label = "Add to schedule" }: { kind: ScheduleKind; refId: string; title: string; label?: string }) {
  const q = new URLSearchParams({ kind, ref: refId, title });
  return <Link to={`/schedule?${q.toString()}`} className="schedule-link">{label}</Link>;
}
