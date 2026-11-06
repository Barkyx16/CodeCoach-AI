/**
 * "Saved for offline": public copies of lessons, questions and coding problems that the learner
 * chose to keep on this device. They live in their own Cache Storage cache, written and read by
 * the page (the service worker never serves or fills it). Only public content goes in: copies
 * are fetched without credentials, so nothing personal (scores, answers) is ever stored here.
 */
import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";

export type OfflineKind = "lesson" | "question" | "problem";

export interface OfflineEntry {
  kind: OfflineKind;
  key: string;
  title: string;
  subtitle: string;
  href: string;
  version: string | null;
  saved_at: string;
  bytes: number;
}

const CACHE = "codecoach-offline-v1";
export const MAX_SAVED = 50;
const path = (kind: OfflineKind, key: string) => `/offline-content/${kind}/${encodeURIComponent(key)}`;

export function offlineSupported(): boolean {
  return typeof caches !== "undefined" && typeof window !== "undefined" && window.isSecureContext;
}

/** Fetch the public copy (never with the learner's credentials) and describe it. */
export async function fetchPublic(kind: OfflineKind, key: string): Promise<{ data: unknown; meta: Omit<OfflineEntry, "saved_at" | "bytes" | "kind" | "key"> }> {
  if (kind === "lesson") {
    const unit = await api.learnUnit(key);
    return { data: unit, meta: { title: unit.title, subtitle: `Lesson · ${unit.career_title}`, href: `/learn/${key}`, version: String(unit.version) } };
  }
  if (kind === "question") {
    const [track, id] = key.split("/") as [string, string];
    const q = await api.publicQuestion(track, id);
    return { data: q, meta: { title: q.title, subtitle: `Question · ${q.career_title}`, href: `/careers/${track}/questions/${id}`, version: null } };
  }
  const p = await api.publicProblem(key);
  return { data: p, meta: { title: p.title, subtitle: "Coding problem", href: `/problems/${key}`, version: null } };
}

async function put(kind: OfflineKind, key: string, data: unknown, meta: Omit<OfflineEntry, "saved_at" | "bytes" | "kind" | "key">): Promise<OfflineEntry> {
  const body = JSON.stringify(data);
  const entry: OfflineEntry = { kind, key, ...meta, saved_at: new Date().toISOString(), bytes: new Blob([body]).size };
  const cache = await caches.open(CACHE);
  await cache.put(path(kind, key), new Response(JSON.stringify({ entry, data }), { headers: { "Content-Type": "application/json" } }));
  return entry;
}

export async function listOffline(): Promise<OfflineEntry[]> {
  if (!offlineSupported()) return [];
  const cache = await caches.open(CACHE);
  const entries: OfflineEntry[] = [];
  for (const request of await cache.keys()) {
    const response = await cache.match(request);
    if (!response) continue;
    try {
      entries.push(((await response.json()) as { entry: OfflineEntry }).entry);
    } catch {
      await cache.delete(request); // unreadable: drop it rather than show something broken
    }
  }
  return entries.sort((a, b) => b.saved_at.localeCompare(a.saved_at));
}

/** Save (or refresh) the public copy. Throws when offline, unsupported, full or the item is gone. */
export async function saveOffline(kind: OfflineKind, key: string): Promise<OfflineEntry> {
  if (!offlineSupported()) throw new Error("This browser can't keep pages for offline use.");
  const existing = await readOffline(kind, key);
  if (!existing && (await listOffline()).length >= MAX_SAVED) {
    throw new Error(`You can keep up to ${MAX_SAVED} items offline. Remove some first.`);
  }
  const { data, meta } = await fetchPublic(kind, key);
  return put(kind, key, data, meta);
}

export async function readOffline<T = unknown>(kind: OfflineKind, key: string): Promise<{ entry: OfflineEntry; data: T } | null> {
  if (!offlineSupported()) return null;
  const response = await (await caches.open(CACHE)).match(path(kind, key));
  if (!response) return null;
  try {
    return (await response.json()) as { entry: OfflineEntry; data: T };
  } catch {
    return null;
  }
}

export async function removeOffline(kind: OfflineKind, key: string): Promise<void> {
  if (!offlineSupported()) return;
  await (await caches.open(CACHE)).delete(path(kind, key));
}

export async function clearOffline(): Promise<void> {
  if (typeof caches !== "undefined") await caches.delete(CACHE);
}

export async function storageEstimate(): Promise<{ usage: number; quota: number } | null> {
  try {
    const estimate = await navigator.storage?.estimate?.();
    return estimate && typeof estimate.usage === "number" && typeof estimate.quota === "number"
      ? { usage: estimate.usage, quota: estimate.quota } : null;
  } catch {
    return null;
  }
}

export interface RevalidateResult {
  refreshed: OfflineEntry[];
  removed: OfflineEntry[];
  unreachable: boolean;
}

/**
 * Back online: refresh each saved copy, one at a time. Anything the server no longer offers
 * (retired, or no longer public: 404/403/410) is removed from the device and reported.
 */
export async function revalidateOffline(): Promise<RevalidateResult> {
  const result: RevalidateResult = { refreshed: [], removed: [], unreachable: false };
  for (const entry of (await listOffline()).slice(0, MAX_SAVED)) {
    try {
      const { data, meta } = await fetchPublic(entry.kind, entry.key);
      result.refreshed.push(await put(entry.kind, entry.key, data, meta));
    } catch (error) {
      if (error instanceof ApiError && [403, 404, 410].includes(error.status)) {
        await removeOffline(entry.kind, entry.key);
        result.removed.push(entry);
      } else {
        result.unreachable = true;
        break; // offline again, or the server is down: stop, try another time
      }
    }
  }
  return result;
}

/**
 * Network first; when the network fails, the saved copy (if there is one). Used by the lesson,
 * question and problem queries, so a saved page opens offline.
 */
export async function withOfflineCopy<T>(kind: OfflineKind, key: string, load: () => Promise<T>): Promise<T> {
  try {
    return await load();
  } catch (error) {
    if (error instanceof ApiError && error.code === "network_error") {
      const saved = await readOffline<T>(kind, key).catch(() => null);
      if (saved) return saved.data;
    }
    throw error;
  }
}
