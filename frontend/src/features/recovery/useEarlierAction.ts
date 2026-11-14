import { useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import type { RequestOutcome } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { findIntent, forgetIntent, type IntentKind, type PendingIntent } from "@/lib/pendingIntents";

export type EarlierAction =
  | { status: "none" }
  | { status: "checking"; intent: PendingIntent }
  | { status: "found"; intent: PendingIntent; outcome: RequestOutcome }
  | { status: "not_found"; intent: PendingIntent }
  | { status: "in_progress"; intent: PendingIntent }
  | { status: "unavailable"; intent: PendingIntent; error: unknown };

/**
 * An action of this kind on this target that was sent before the page was reloaded or closed,
 * and never answered (Volume 8, prompt 1). Once the account is known, the server is asked what
 * its key made: a read, never a resend. Found or not found, the record is then forgotten, so the
 * next reload doesn't ask again; the answer stays on screen for this visit. Unreachable: the
 * record is kept and `recheck` asks again. Still being answered (a hint or review in flight,
 * which has no record until its answer does: Volume 8, prompt 2): kept, and asked again after
 * the server's wait, once by itself; then `recheck`.
 */
export function useEarlierAction(kind: IntentKind, target: string | null): EarlierAction & { recheck: () => void; dismiss: () => void } {
  const { user, isRestoring } = useAuth();
  const userId = isRestoring ? undefined : (user?.id ?? null);
  const [seen, setSeen] = useState<{ userId: string | null | undefined; target: string | null; intent: PendingIntent | null }>(
    () => ({ userId, target, intent: userId && target ? findIntent(userId, kind, target) : null }),
  );
  if (seen.userId !== userId || seen.target !== target) {
    setSeen({ userId, target, intent: userId && target ? findIntent(userId, kind, target) : null });
  }
  const intent = seen.intent;
  const query = useQuery({
    queryKey: ["request-outcome", userId, intent?.key],
    enabled: !!intent && !!userId,
    // In progress: ask once more by itself after the server's wait (a few seconds).
    retry: (count, e) => count < 1 && inProgress(e),
    retryDelay: (_count, e) => Math.min(10, (e instanceof ApiError && e.retryAfterSeconds) || 2) * 1000,
    staleTime: Infinity,
    queryFn: async () => {
      try {
        const outcome = await api.requestOutcome(intent!.key);
        forgetIntent(userId, kind, target!, intent!.key);
        return outcome;
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) forgetIntent(userId, kind, target!, intent!.key);
        throw e;
      }
    },
  });
  const recheck = useCallback(() => void query.refetch(), [query]);
  const dismiss = useCallback(() => {
    if (intent) forgetIntent(userId, kind, target!, intent.key);
    setSeen((s) => ({ ...s, intent: null }));
  }, [intent, userId, kind, target]);

  let state: EarlierAction;
  if (!intent) state = { status: "none" };
  else if (query.data) state = { status: "found", intent, outcome: query.data };
  else if (query.error instanceof ApiError && query.error.status === 404) state = { status: "not_found", intent };
  else if (query.isError && inProgress(query.error)) state = { status: "in_progress", intent };
  else if (query.isError) state = { status: "unavailable", intent, error: query.error };
  else state = { status: "checking", intent };
  return { ...state, recheck, dismiss };
}

const inProgress = (e: unknown) => e instanceof ApiError && e.code === "request_in_progress";
