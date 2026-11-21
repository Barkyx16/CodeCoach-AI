import type { ActivityFilters } from "@/api/endpoints";
import type { ActivityStatus, ActivityType } from "@/api/types";

export const PAGE_SIZE = 15;
const KEYS = ["career", "type", "status", "skill", "since", "until", "q"] as const;

/** History filters live in the URL, so Back, reload and shared links all restore them. */
export function filtersFromParams(params: URLSearchParams): ActivityFilters & { page: number } {
  const page = Math.max(1, Number(params.get("page")) || 1);
  return {
    career: params.get("career") ?? undefined,
    type: (params.get("type") as ActivityType | null) ?? undefined,
    status: (params.get("status") as ActivityStatus | null) ?? undefined,
    skill: params.get("skill") ?? undefined,
    since: params.get("since") ?? undefined,
    until: params.get("until") ?? undefined,
    q: params.get("q") ?? undefined,
    page,
  };
}

export function hasFilters(params: URLSearchParams): boolean {
  return KEYS.some((k) => params.get(k));
}

export { KEYS as FILTER_KEYS };
