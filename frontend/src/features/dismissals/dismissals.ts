import { useQuery } from "@tanstack/react-query";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";

/**
 * Suggestions dismissed with "Not now", kept with the account so every device respects them
 * (Volume 15, prompt 2; docs/FOLLOW_UPS.md, "Not now"). A key names the suggestion, not the item it
 * was offered on.
 */
export const dismissalsKey = ["me", "dismissals"] as const;
export const questionFollowUpKey = (track: string, from: string, to: string) => `question-follow-up:${track}/${from}>${to}`;
export const planChangeKey = (track: string, version: number) => `plan-change:${track}@${version}`;

export function useDismissals(enabled = true) {
  return useQuery({ queryKey: dismissalsKey, queryFn: () => api.dismissals(), enabled });
}

const carried = new Set<string>(); // once per account per page load

/** True the first time for an account in this page load. */
export function claimCarryOver(userId: string): boolean {
  if (carried.has(userId)) return false;
  carried.add(userId);
  return true;
}

export function resetCarryOverForTests() {
  carried.clear();
}

// What this browser kept before dismissals moved to the account. Carried over once, then cleared.
const FOLLOW_UPS = (userId: string) => `codecoach.followups.dismissed.v1.${userId}`;
const PLAN_SEEN = "codecoach.plan.seen.";

/** A browser-only dismissal from before, carried over to the account once, then the browser copy is
 * cleared. One request per key: a key the server refuses (a relationship that no longer exists) is
 * cleared too, since it can never be carried; a lost connection keeps it for next time. */
export async function carryOverLocalDismissals(userId: string): Promise<number> {
  let store: Storage;
  try {
    store = window.localStorage;
  } catch {
    return 0; // storage blocked: nothing was kept here
  }
  const found: { storageKey: string; keys: string[] }[] = [];
  try {
    const raw = store.getItem(FOLLOW_UPS(userId));
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    const keys = Array.isArray(parsed)
      ? parsed.filter((k): k is string => typeof k === "string" && /^[^/]+\/[^>]+>.+$/.test(k)).slice(0, 200)
      : [];
    if (raw !== null) found.push({ storageKey: FOLLOW_UPS(userId), keys: keys.map((k) => `question-follow-up:${k}`) });
    for (let i = 0; i < store.length; i++) {
      const k = store.key(i);
      if (!k?.startsWith(PLAN_SEEN)) continue;
      const version = Number(store.getItem(k));
      const track = k.slice(PLAN_SEEN.length);
      found.push({ storageKey: k, keys: Number.isInteger(version) && version > 0 ? [planChangeKey(track, version)] : [] });
    }
  } catch {
    return 0;
  }
  let carried = 0;
  for (const { storageKey, keys } of found) {
    let keep = false;
    for (const key of keys) {
      try {
        await api.dismiss([{ key, offered_on: null }]);
        carried += 1;
      } catch (e) {
        if (!(e instanceof ApiError) || e.status >= 500 || e.code === "network_error") keep = true;
      }
    }
    if (!keep) {
      try { store.removeItem(storageKey); } catch { /* cleared next time */ }
    }
  }
  return carried;
}
