import type { Competency, StoryContext, StorySection } from "@/api/types";

export const COMPETENCIES: Competency[] = [
  "teamwork", "conflict", "leadership", "prioritization", "mistakes",
  "communication", "problem_solving", "adaptability", "care", "initiative",
];

export const COMPETENCY_LABEL: Record<Competency, string> = {
  teamwork: "Teamwork",
  conflict: "Handling conflict",
  leadership: "Leadership",
  prioritization: "Prioritising",
  mistakes: "Handling a mistake",
  communication: "Communication",
  problem_solving: "Problem solving",
  adaptability: "Adapting to change",
  care: "Patient or customer care",
  initiative: "Taking initiative",
};

export const CONTEXT_LABEL: Record<StoryContext, string> = {
  work: "Work",
  study: "Study",
  volunteering: "Volunteering",
  personal: "Personal project",
  other: "Something else",
};

export const SECTION_LABEL: Record<StorySection, string> = {
  situation: "Situation",
  task: "Task",
  action: "Action",
  result: "Result",
  reflection: "Reflection (optional)",
};

/** Neutral prompts: they help describe the learner's own part, and never suggest achievements. */
export const SECTION_PROMPT: Record<StorySection, string> = {
  situation: "Where were you, and what was going on? A sentence or two is enough.",
  task: "What were you responsible for, or what needed to happen?",
  action: "What did you do? Say “I” for your part; it's fine to mention what others did too.",
  result: "What happened in the end? Describe it in your own words; a number isn't required.",
  reflection: "What did you learn, or what would you do differently?",
};

export const SECTIONS: StorySection[] = ["situation", "task", "action", "result", "reflection"];
