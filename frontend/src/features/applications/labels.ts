import type { ApplicationStage, EventKind } from "@/api/types";

export const STAGES: ApplicationStage[] = ["saved", "applied", "interviewing", "offer", "closed", "withdrawn"];

export const STAGE_LABEL: Record<ApplicationStage, string> = {
  saved: "Saved",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  closed: "Closed",
  withdrawn: "Withdrawn",
};

/** What each stage means: always what the learner recorded, never something CodeCoach inferred. */
export const STAGE_HINT: Record<ApplicationStage, string> = {
  saved: "Interested, not applied yet",
  applied: "You recorded that you applied",
  interviewing: "In the interview process",
  offer: "You recorded an offer",
  closed: "No longer active",
  withdrawn: "You withdrew",
};

export const EVENT_KIND_LABEL: Record<EventKind, string> = {
  phone_screen: "Phone screen",
  interview: "Interview",
  assessment: "Assessment",
  other: "Other",
};
