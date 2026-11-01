import type { InterviewPhase } from "@/api/types";

export const PHASES: { id: InterviewPhase; label: string }[] = [
  { id: "clarify", label: "Clarify" },
  { id: "approach", label: "Approach" },
  { id: "coding", label: "Code" },
  { id: "complexity", label: "Complexity" },
  { id: "wrap_up", label: "Test & wrap up" },
];

export const DIMENSION_LABELS: Record<string, string> = {
  problem_solving: "Problem solving",
  communication: "Communication",
  code_quality: "Code quality",
  complexity_analysis: "Complexity analysis",
  testing: "Testing",
};

export const OVERALL_LABELS: Record<string, { label: string; tone: string }> = {
  strong: { label: "Strong", tone: "success" },
  solid: { label: "Solid", tone: "info" },
  developing: { label: "Developing", tone: "warning" },
  needs_work: { label: "Needs work", tone: "danger" },
};

export const SCORE_WORDS = ["", "Needs work", "Developing", "Solid", "Strong"];
