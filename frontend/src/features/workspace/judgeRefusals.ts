import { ApiError } from "@/api/client";

/** The judge's refusals of a run or submission: nothing was queued (see JudgeRecovery). */
export const JUDGE_REFUSALS = ["submission_pending", "judge_busy", "judge_unavailable", "execution_disabled"];

/** Whether "Try again" can help: not while the earlier one is still being judged, nor where code can't run. */
export function judgeRetryHelps(error: unknown): boolean {
  return !(error instanceof ApiError && ["submission_pending", "execution_disabled"].includes(error.code));
}
