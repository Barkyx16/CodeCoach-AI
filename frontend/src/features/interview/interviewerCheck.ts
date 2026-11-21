import { useCallback, useState } from "react";

import type { AnswerSource, CoachPreview } from "@/api/types";
import { storage } from "@/lib/storage";

/**
 * What the coding interviewer reads, checked before it's sent (Volume 14, prompt 3;
 * docs/COACH_CONTEXT.md, "The coding interviewer"). One action away by default; a learner who
 * wants to check every message, and the feedback, can turn that on. The choice is kept in this
 * browser only (a convenience, not account data).
 */
export const CHECK_EACH_KEY = "codecoach.interview-check-each";

export function useCheckEach(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(() => storage.get(CHECK_EACH_KEY) === "on");
  const set = useCallback((next: boolean) => {
    setOn(next);
    storage.set(CHECK_EACH_KEY, next ? "on" : "off"); // private mode: this visit only
  }, []);
  return [on, set];
}

export type Ending = "finished" | "abandoned";

/** A preview on screen, with what it was built from (to tell when the page no longer matches it). */
export type Checked =
  | { kind: "message"; data: CoachPreview; message: string; code: string; source: AnswerSource; turns: number }
  | { kind: "feedback"; ending: Ending; data: CoachPreview; code: string | null; turns: number };

export const INTERVIEWER_REFUSED =
  "What the interviewer would read changed since you checked it, so nothing was sent. This is what it would read now.";
export const MOVED_ON = "The conversation moved on since this was checked, so it isn't what would be sent.";
export const MESSAGE_CHANGED = "Your message changed since this was checked, so it isn't what would be sent.";

/** Why what's on the page isn't what `checked` shows, or null. */
export function staleness(checked: Checked, now: { message: string; code: string; turns: number }, codeChanged: string): string | null {
  if (now.turns !== checked.turns) return MOVED_ON;
  if (checked.kind === "message" && now.message.trim() !== checked.message) return MESSAGE_CHANGED;
  if (checked.code !== null && now.code !== checked.code) return codeChanged;
  return null;
}

export const SEND_LABEL: Record<"message" | Ending, string> = {
  message: "Send to the interviewer",
  finished: "Finish and get feedback",
  abandoned: "End and get feedback",
};

export function feedbackCost(remaining: number): string {
  return remaining > 0
    ? `Checking this is free. The feedback uses one of the ${remaining} coaching request${remaining === 1 ? "" : "s"} you have left today.`
    : "Checking this is free. You've no coaching requests left today, so the built-in interviewer scores it, free.";
}
