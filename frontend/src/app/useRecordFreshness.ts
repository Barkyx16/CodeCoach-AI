import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { useAuth } from "@/auth/useAuth";
import { listen } from "@/lib/recordSignals";

/**
 * Same-account record hints from this browser's other tabs (docs/FRESHNESS.md), turned into
 * targeted cache invalidation: only what the change touches, and only the queries on screen are
 * fetched again (the rest are marked stale and fetched when next shown). The data itself always
 * comes from the server, asked as this account; the hint carries none.
 */
export function useRecordFreshness(): void {
  const { user } = useAuth();
  const qc = useQueryClient();
  const account = user?.id;
  useEffect(() => {
    if (!account) return;
    return listen(account, (s) => {
      if (s.type !== "story") return;
      void qc.invalidateQueries({ queryKey: ["me", "story", s.id] }); // the story, where it's used, its versions
      void qc.invalidateQueries({ queryKey: ["me", "stories"] });
      void qc.invalidateQueries({ queryKey: ["me", "recent-work"] });
      void qc.invalidateQueries({ queryKey: ["me", "workspace-search"] }); // results showing its title or words
      // Counts change when one is created (sent as "saved") or deleted; archiving keeps it counted.
      if (s.change === "saved" || s.change === "deleted") void qc.invalidateQueries({ queryKey: ["me", "data-summary"] });
      // Pages that show a story's title read it when opened: marked stale, not fetched now.
      void qc.invalidateQueries({ queryKey: ["me", "application"], refetchType: "none" });
      void qc.invalidateQueries({ queryKey: ["me", "kit"], refetchType: "none" });
    });
  }, [account, qc]);
}
