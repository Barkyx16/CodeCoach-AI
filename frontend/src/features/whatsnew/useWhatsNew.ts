import { useMemo, useSyncExternalStore } from "react";

import { useCapabilities, useCareers } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { DEFAULT_TRACK } from "@/features/careers/practiceTrack";

import { ENTRIES, type ReleaseEntry } from "./releases";
import {
  BUILD_RELEASE, parseSeen, readSeenRaw, type SeenState, seenRelease, shippedEntries, subscribeSeen, type WhatsNewContext,
} from "./whatsNew";

/** This build's entries (the same list for everyone; what each opens is worked out per learner). */
export function useShippedEntries(): ReleaseEntry[] {
  return useMemo(() => shippedEntries(ENTRIES, BUILD_RELEASE), []);
}

/** What this account has seen of What's new in this browser; nothing for a visitor. Follows
 * changes from this tab and others, and switches with the account. */
export function useSeen(userId: string | undefined): SeenState {
  const raw = useSyncExternalStore(subscribeSeen, () => (userId ? readSeenRaw(userId) : null));
  return useMemo(() => (userId ? parseSeen(raw) : { kind: "none" as const }), [raw, userId]);
}

/** The newest release counted as seen for this account, or null (a visitor, or storage refused). */
export function useSeenRelease(userId: string | undefined): { state: SeenState; release: number | null } {
  const state = useSeen(userId);
  return { state, release: userId ? seenRelease(state, BUILD_RELEASE) : null };
}

/** The learner's sign-in, career and server state, by the command palette's rules. `careersNeeded`
 * false skips asking for the careers list (the coding check then falls back to the default track). */
export function useWhatsNewContext(careersNeeded = true): { context: WhatsNewContext; careerTitle?: string; userId?: string; careerKnown: boolean } {
  const { user, isAuthenticated } = useAuth();
  const capabilities = useCapabilities(careersNeeded);
  const careers = useCareers(careersNeeded);
  const track = user?.career_track ?? DEFAULT_TRACK;
  const career = careers.data?.find((c) => c.slug === track);
  return {
    context: {
      signedIn: isAuthenticated,
      coding: career ? career.has_coding : track === DEFAULT_TRACK,
      executionEnabled: capabilities.data?.execution_enabled ?? true,
      demoMode: capabilities.data?.demo_mode === true,
    },
    careerTitle: career?.title,
    userId: isAuthenticated ? user?.id : undefined,
    careerKnown: Boolean(career),
  };
}
