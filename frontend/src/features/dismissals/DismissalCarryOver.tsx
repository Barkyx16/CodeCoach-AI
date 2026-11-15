import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { useAuth } from "@/auth/useAuth";

import { carryOverLocalDismissals, claimCarryOver, dismissalsKey } from "./dismissals";

/** Carries this browser's dismissals from before (kept only here) over to the account, once. */
export function DismissalCarryOver() {
  const { user, isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const id = isAuthenticated && !user?.is_guest ? user?.id : undefined;
  useEffect(() => {
    if (!id || !claimCarryOver(id)) return;
    void carryOverLocalDismissals(id).then((n) => {
      if (n > 0) {
        void queryClient.invalidateQueries({ queryKey: dismissalsKey });
        void queryClient.invalidateQueries({ queryKey: ["me", "follow-up"] });
      }
    });
  }, [id, queryClient]);
  return null;
}

