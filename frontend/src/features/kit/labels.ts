import type { Kit } from "@/api/types";

export type KitFormat = Kit["format"];
export type QuestionGroup = Kit["questions"][number]["group"];

export const FORMAT_LABEL: Record<KitFormat, string> = { remote: "Remote (video call)", in_person: "In person", phone: "By phone", unknown: "Not known yet" };

export const GROUP_LABEL: Record<QuestionGroup, string> = {
  role: "The role", team: "The team", training: "Training and support", workflow: "How the work runs", next_steps: "Next steps", other: "Other",
};

/** What goes in the printed pack. Private details are off until chosen. */
export interface PrintChoice {
  when: boolean;
  location: boolean;
  meetingLink: boolean;
  interviewers: boolean;
  questions: boolean;
  checklist: boolean;
  stories: boolean;
  notes: boolean;
}

export const DEFAULT_PRINT: PrintChoice = {
  when: true, location: true, meetingLink: false, interviewers: false, questions: true, checklist: true, stories: true, notes: false,
};

export const PRINT_LABEL: Record<keyof PrintChoice, string> = {
  when: "Date, time and format",
  location: "Location",
  meetingLink: "Meeting link (private)",
  interviewers: "Interviewer names (private)",
  questions: "Questions you'll ask",
  checklist: "Checklist (what's left)",
  stories: "Your examples",
  notes: "Your notes (private)",
};
