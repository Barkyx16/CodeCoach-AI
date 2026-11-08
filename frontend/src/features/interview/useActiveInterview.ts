import { useInterviews } from "@/api/queries";

/**
 * The interview in progress, if any, so a start page can offer to resume it instead of a Start
 * button that can only fail (one interview at a time). Only one can be in progress, so it's the
 * most recent; the list expires overdue ones before answering, so "in progress" is current. The
 * query is the one "Recent interviews" already makes.
 */
export function useActiveInterviewId(): string | null {
  const recent = useInterviews({ page_size: 5 });
  return recent.data?.items.find((iv) => iv.status === "in_progress")?.id ?? null;
}
