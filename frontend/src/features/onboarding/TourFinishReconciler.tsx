import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/endpoints";
import { useUpdateOnboarding } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";

import { clearFinishPending, isFinishPending } from "./finishIntent";

/**
 * On load, for the signed-in account only: if a finish of the introduction may not have reached
 * the server (finishIntent.ts), ask the server what it has (not the cache, which already shows the
 * optimistic finish). A tour still running or paused there gets "complete" sent again; anything
 * else means the server has its own answer, and the note is dropped. Once per account per load.
 */
export function TourFinishReconciler() {
  const { user, isAuthenticated } = useAuth();
  const qc = useQueryClient();
  const update = useUpdateOnboarding(user?.id);
  const checked = useRef<string | null>(null);
  const accountId = isAuthenticated ? user?.id : undefined;
  // Who is signed in now: an answer that arrives after an account change is for someone else.
  // (A ref, not an effect cleanup flag: React runs effects twice in development, and the second
  // run must not discard the first run's only request.)
  const current = useRef(accountId);
  useEffect(() => {
    current.current = accountId;
  }, [accountId]);

  useEffect(() => {
    if (!accountId || checked.current === accountId || !isFinishPending(accountId)) return;
    checked.current = accountId;
    api.onboarding().then(
      (server) => {
        if (current.current !== accountId) return;
        if (server.tour_status === "in_progress" || server.tour_status === "paused") {
          update.mutate({ tour: "complete" });
        } else {
          clearFinishPending(accountId);
          qc.setQueryData(["me", "onboarding"], server);
        }
      },
      () => {
        /* couldn't ask: keep the note for the next load */
      },
    );
  }, [accountId]); // eslint-disable-line react-hooks/exhaustive-deps

  return null;
}
