import { useInterviews } from "@/api/queries";
import type { InterviewSummary } from "@/api/types";

/**
 * The interview in progress, if any, so a start page can offer to resume it instead of a Start
 * button that can only fail (one interview at a time, from any tab or device). Only one can be in
 * progress, so it's the most recent; the list expires overdue ones before answering, so "in
 * progress" is current, and it's asked again when the learner comes back to this tab (another
 * device may have finished it). Its summary says what it is, how far along, the time left and the
 * last activity. The query is the one "Recent interviews" already makes.
 */
export function useActiveInterview(): InterviewSummary | null {
  const recent = useInterviews({ page_size: 5 }, true, true);
  return recent.data?.items.find((iv) => iv.status === "in_progress") ?? null;
}

export function useActiveInterviewId(): string | null {
  return useActiveInterview()?.id ?? null;
}
