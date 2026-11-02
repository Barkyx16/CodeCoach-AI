import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { useStartInterview } from "@/api/queries";
import type { PlanItem } from "@/api/types";

/** Opens an activity: its page, or (for interview activities) a new round started on the server. */
export function useStartActivity() {
  const navigate = useNavigate();
  const start = useStartInterview();
  const activeId = start.error instanceof ApiError && start.error.code === "interview_in_progress"
    ? (start.error.details as { interview_id?: string } | null)?.interview_id ?? null
    : null;

  async function open(item: PlanItem) {
    if (item.href) {
      navigate(item.href, { state: { from: "/dashboard", fromLabel: "Back to your plan" } });
      return;
    }
    if (!item.round) return;
    const r = item.round;
    try {
      const iv = await start.mutateAsync({
        kind: "questions", purpose: r.purpose, track: r.track, difficulty: r.difficulty as "easy" | null | undefined,
        question_ids: r.question_ids ?? null, duration_minutes: r.duration_minutes,
      });
      navigate(`/interviews/${iv.id}`);
    } catch {
      /* shown by the caller via `error` / `activeId` */
    }
  }

  return { open, pending: start.isPending, error: activeId ? null : start.error, activeId };
}
