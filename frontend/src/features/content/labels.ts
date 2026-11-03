import type { ReportCategory, ReportStatusValue } from "@/api/types";

export const CATEGORY_LABEL: Record<ReportCategory, string> = {
  ambiguous_wording: "Ambiguous or unclear wording",
  incorrect_example: "Incorrect example or answer",
  outdated_guidance: "Outdated guidance",
  wrong_career_topic: "Wrong career or topic",
  accessibility: "Accessibility problem",
  technical_bug: "Technical bug",
  other: "Something else",
};

export const STATUS_LABEL: Record<ReportStatusValue, string> = {
  open: "Received",
  investigating: "Being looked at",
  resolved: "Resolved",
  not_actionable: "Closed without a change",
};

export const STATUS_TONE: Record<ReportStatusValue, string> = {
  open: "info",
  investigating: "warning",
  resolved: "success",
  not_actionable: "neutral",
};
