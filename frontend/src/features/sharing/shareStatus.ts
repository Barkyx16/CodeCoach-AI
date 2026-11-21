import type { ShareSummary } from "@/api/types";

export const STATUS_LABEL: Record<ShareSummary["status"], string> = {
  active: "Link on",
  closed: "Not taking feedback",
  revoked: "Link turned off",
  expired: "Link expired",
};

export const STATUS_TONE: Record<ShareSummary["status"], "success" | "info" | "warning" | undefined> = {
  active: "success",
  closed: "info",
  revoked: "warning",
  expired: undefined,
};

export function feedbackCount(n: number): string {
  return n === 0 ? "No feedback yet" : `${n} ${n === 1 ? "response" : "responses"}`;
}
