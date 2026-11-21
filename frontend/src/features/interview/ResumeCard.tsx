import { Link } from "react-router-dom";

import type { InterviewSummary } from "@/api/types";

import { describeLive } from "./resumeContext";

/** Shown instead of a Start that can only fail (one interview at a time). `alert` when it's the
 * answer to a Start the learner just tried (a 409 from another tab or device's interview). */
export function ResumeCard({ id, summary, alert = false }: { id: string; summary: InterviewSummary | null; alert?: boolean }) {
  return (
    <div className="banner banner--warning" role={alert ? "alert" : "status"}>
      You already have an interview in progress. <Link to={`/interviews/${id}`}>Resume it</Link>, or end it
      there to start another.
      {summary && <span className="resume-card__context"> {describeLive(summary).join(" · ")}.</span>}
    </div>
  );
}
