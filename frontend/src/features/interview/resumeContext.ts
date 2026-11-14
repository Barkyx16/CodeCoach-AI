import type { InterviewSummary } from "@/api/types";
import { timeAgo, titleCase } from "@/lib/format";

import { formatClock } from "./useCountdown";

/** Enough to recognize the interview in progress before resuming it: what it is, how far along,
 * the time the server says is left, and when it was last touched (from any tab or device). */
export function describeLive(s: InterviewSummary, now: Date = new Date()): string[] {
  const parts = [
    s.kind === "questions"
      ? `${s.career_title ?? titleCase(s.track ?? "Career")} interview`
      : `${s.problem?.title ?? "Coding"} coding interview`,
  ];
  if (s.progress_total) parts.push(`${s.progress_done ?? 0} of ${s.progress_total} questions done`);
  else if (s.progress_done != null) parts.push(`${s.progress_done} ${s.progress_done === 1 ? "message" : "messages"} sent`);
  if (s.seconds_remaining != null) parts.push(`${formatClock(s.seconds_remaining)} left`);
  if (s.last_activity_at) parts.push(`last active ${timeAgo(s.last_activity_at, now)}`);
  return parts;
}

/** The interview a Start was refused for: the 409 carries its id and a summary to show. */
export function conflictInterview(details: unknown): { id: string; summary: InterviewSummary | null } | null {
  const d = details as { interview_id?: string; interview?: InterviewSummary } | null;
  return d?.interview_id ? { id: d.interview_id, summary: d.interview ?? null } : null;
}
