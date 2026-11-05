import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { useStartInterview } from "@/api/queries";
import type { PlanItem } from "@/api/types";
import { useAuth } from "@/auth/useAuth";

import { rememberPlanOrigin } from "./planOrigin";

/** Where an activity opened from the plan should offer to go back to. */
export function planReturnState(from: string, item: PlanItem) {
  return { from, fromLabel: from === "/plan" ? "Back to your plan" : "Back to your dashboard", planItemId: item.id };
}

/**
 * Opens an activity: its page, or (for interview activities) a new round started on the server.
 * Either way it remembers which plan activity led there (see planOrigin.ts), so the destination
 * can lead back to the plan's next step.
 */
export function useStartActivity() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { user } = useAuth();
  const start = useStartInterview();
  const activeId = start.error instanceof ApiError && start.error.code === "interview_in_progress"
    ? (start.error.details as { interview_id?: string } | null)?.interview_id ?? null
    : null;

  const remember = (item: PlanItem, target: string) => {
    if (user) rememberPlanOrigin({ userId: user.id, itemId: item.id, title: item.title, target, from: pathname });
  };

  async function open(item: PlanItem) {
    if (item.href) {
      remember(item, item.href);
      navigate(item.href, { state: planReturnState(pathname, item) });
      return;
    }
    if (!item.round) return;
    const r = item.round;
    try {
      const iv = await start.mutateAsync({
        kind: "questions", purpose: r.purpose, track: r.track, difficulty: r.difficulty as "easy" | null | undefined,
        question_ids: r.question_ids ?? null, duration_minutes: r.duration_minutes,
      });
      remember(item, `/interviews/${iv.id}`);
      navigate(`/interviews/${iv.id}`, { state: planReturnState(pathname, item) });
    } catch {
      /* shown by the caller via `error` / `activeId` (an interview already in progress isn't duplicated) */
    }
  }

  return { open, pending: start.isPending, error: activeId ? null : start.error, activeId, remember };
}
