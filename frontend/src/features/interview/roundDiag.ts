import { useEffect } from "react";

import { ApiError } from "@/api/client";
import type { Interview } from "@/api/types";
import { diag } from "@/lib/diagnostics";

/** What a live round shows right now (for diagnostics and for choosing what to render). */
export type RoundView = "question" | "followup" | "empty" | "results";

function where(iv: Interview) {
  return {
    status: iv.status,
    current: iv.questions.find((q) => q.status === "current")?.index ?? null,
    pending: iv.round_format?.pending_followup?.question_index ?? null,
  };
}

/** Run one round action and leave a breadcrumb for its start and outcome (ids and codes only). */
export async function tracedRoundAction(
  action: "answer" | "skip" | "reply" | "skip_followup",
  interviewId: string,
  index: number,
  run: () => Promise<Interview>,
): Promise<Interview> {
  diag("round_action", { action, interviewId, index, phase: "start" });
  try {
    const iv = await run();
    diag("round_action", { action, interviewId, index, phase: "done", ...where(iv) });
    return iv;
  } catch (error) {
    diag("round_action", {
      action, interviewId, index, phase: "error",
      code: error instanceof ApiError ? error.code : "unknown",
      httpStatus: error instanceof ApiError ? error.status : null,
      requestId: error instanceof ApiError ? error.requestId : null,
    });
    throw error;
  }
}

/** Record each change of what the round shows. */
export function useRoundViewDiag(iv: Interview, view: RoundView): void {
  const { status, current, pending } = where(iv);
  useEffect(() => {
    diag("round_view", { interviewId: iv.id, view, status, current, pending });
  }, [iv.id, view, status, current, pending]);
}
