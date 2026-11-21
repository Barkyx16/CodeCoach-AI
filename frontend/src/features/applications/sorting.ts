import type { ApplicationSummary } from "@/api/types";

import { STAGES } from "./labels";

export type SortKey = "updated" | "role" | "employer" | "stage" | "applied" | "due";

export function sortApps(list: ApplicationSummary[], key: SortKey, dir: "asc" | "desc"): ApplicationSummary[] {
  const value = (a: ApplicationSummary): string => {
    switch (key) {
      case "role": return a.role_title.toLowerCase();
      case "employer": return a.employer.toLowerCase();
      case "stage": return String(STAGES.indexOf(a.stage)).padStart(2, "0");
      case "applied": return a.applied_on ?? "";
      case "due": return a.next_action_due ?? "";
      default: return a.updated_at;
    }
  };
  // Stable: ties keep their order; unknown dates go last whichever way you sort.
  return [...list].sort((a, b) => {
    const va = value(a), vb = value(b);
    if (!va && vb) return 1;
    if (va && !vb) return -1;
    return (va < vb ? -1 : va > vb ? 1 : 0) * (dir === "asc" ? 1 : -1);
  });
}
