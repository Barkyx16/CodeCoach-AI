import type { ApplicationStage, ReflectionOutcome } from "@/api/types";

export const OUTCOME_LABEL: Record<ReflectionOutcome, string> = {
  unknown: "Not known yet",
  awaiting: "Waiting to hear",
  another_round: "Invited to another round",
  offer: "Offer",
  not_selected: "Not selected",
  withdrawn: "I withdrew",
};

/** Mirrors the server: only these outcomes can move the application, and only when asked. */
export const STAGE_FOR: Partial<Record<ReflectionOutcome, ApplicationStage>> = {
  another_round: "interviewing", offer: "offer", not_selected: "closed", withdrawn: "withdrawn",
};

export { STAGE_LABEL } from "@/features/applications/labels";
