import { newRequestKey } from "./requestKey";

/**
 * Unresolved actions that survive a reload (Volume 8, prompt 1; docs/RECOVERY.md).
 *
 * Before a keyed request is sent, a small record is written to this browser: the account, what
 * kind of action, its target, the request key, and a fingerprint of exactly what was sent. Never
 * the content itself (the learner's text stays in its own draft storage), never a credential. If
 * the reply is lost and the page reloads, the record lets the page ask the server what that key
 * made (a read, GET /me/requests/{key}) instead of sending again under a new key.
 *
 * - **Per account.** Records live under the account's id; another account never reads them, and a
 *   deliberate sign-out deletes them.
 * - **Bounded.** At most 20 records per account, each kept 24 hours; the oldest go first.
 * - **One key per intent, across tabs.** The same kind, target and fingerprint reuses the stored
 *   key, so two tabs (or a retry after a reload) send the same key and the server makes it once.
 *   Changed content is a new intent with a new key.
 * - **Honest when storage fails.** `rememberIntent` says whether the record was kept; when it
 *   wasn't, the page doesn't promise recovery after a reload.
 */
export type IntentKind = "submission" | "run" | "hint" | "review" | "story" | "note_copy";

export interface PendingIntent {
  v: 1;
  kind: IntentKind;
  target: string;
  key: string;
  fingerprint: string;
  sentAt: number;
}

const PREFIX = "codecoach.pending.v1.";
const MAX = 20;
export const INTENT_TTL_MS = 24 * 60 * 60 * 1000;

type Store = Record<string, PendingIntent>;
const slot = (kind: IntentKind, target: string) => `${kind}:${target}`;

function read(userId: string): Store {
  try {
    const raw = window.localStorage.getItem(PREFIX + userId);
    const value: unknown = raw ? JSON.parse(raw) : {};
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    const now = Date.now();
    const kept: Store = {};
    for (const [k, r] of Object.entries(value as Record<string, unknown>)) {
      const i = r as Partial<PendingIntent>;
      if (i && i.v === 1 && typeof i.key === "string" && typeof i.fingerprint === "string" && typeof i.sentAt === "number"
          && typeof i.kind === "string" && typeof i.target === "string" && now - i.sentAt < INTENT_TTL_MS) {
        kept[k] = i as PendingIntent;
      }
    }
    return kept;
  } catch {
    return {};
  }
}

function write(userId: string, store: Store): boolean {
  try {
    const entries = Object.entries(store).sort(([, a], [, b]) => b.sentAt - a.sentAt).slice(0, MAX);
    if (entries.length) window.localStorage.setItem(PREFIX + userId, JSON.stringify(Object.fromEntries(entries)));
    else window.localStorage.removeItem(PREFIX + userId);
    return true;
  } catch {
    return false;
  }
}

/** A short, stable fingerprint of what's sent (not a secret: only for "is this the same request?"). */
export function fingerprint(...parts: (string | number | null | undefined)[]): string {
  const text = JSON.stringify(parts);
  let h1 = 0xdeadbeef ^ text.length;
  let h2 = 0x41c6ce57 ^ text.length;
  for (let i = 0; i < text.length; i++) {
    const c = text.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 2654435761);
    h2 = Math.imul(h2 ^ c, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return `${(h2 >>> 0).toString(16).padStart(8, "0")}${(h1 >>> 0).toString(16).padStart(8, "0")}:${text.length}`;
}

export function findIntent(userId: string | null | undefined, kind: IntentKind, target: string): PendingIntent | null {
  if (!userId) return null;
  return read(userId)[slot(kind, target)] ?? null;
}

/**
 * The key for this exact request: an unresolved one already stored for the same content (from
 * this tab, another tab, or before a reload) is reused; otherwise a new one. Then the record is
 * written, before anything is sent. `kept` is false when this browser couldn't store it.
 */
export function keyForIntent(userId: string, kind: IntentKind, target: string, print: string): { key: string; kept: boolean } {
  const store = read(userId);
  const earlier = store[slot(kind, target)];
  const key = earlier && earlier.fingerprint === print ? earlier.key : newRequestKey();
  store[slot(kind, target)] = { v: 1, kind, target, key, fingerprint: print, sentAt: earlier?.key === key ? earlier.sentAt : Date.now() };
  const kept = write(userId, store);
  // Another tab may have written the same intent a moment ago: whichever key is stored now wins,
  // so both tabs send the same one.
  const now = read(userId)[slot(kind, target)];
  return { key: kept && now && now.fingerprint === print ? now.key : key, kept };
}

/** The action is resolved (answered, refused, or checked): forget it. Only the same key is removed. */
export function forgetIntent(userId: string | null | undefined, kind: IntentKind, target: string, key?: string): void {
  if (!userId) return;
  const store = read(userId);
  const current = store[slot(kind, target)];
  if (!current || (key && current.key !== key)) return;
  delete store[slot(kind, target)];
  write(userId, store);
}

/** This account's unresolved actions on this device, newest first ("Your data" lists them). */
export function listIntents(userId: string): PendingIntent[] {
  return Object.values(read(userId)).sort((a, b) => b.sentAt - a.sentAt);
}

/**
 * Remove chosen records on purpose ("Your data"). The actions themselves aren't touched: one still
 * in flight finishes as it would, but after a reload the page can no longer ask what it made.
 * False when this browser refused the change.
 */
export function forgetIntents(userId: string, chosen: { kind: IntentKind; target: string }[]): boolean {
  const store = read(userId);
  for (const c of chosen) delete store[slot(c.kind, c.target)];
  return write(userId, store);
}

/** A deliberate sign-out: this account's records go, with their metadata. */
export function forgetAllIntents(userId: string | null | undefined): void {
  if (!userId) return;
  try {
    window.localStorage.removeItem(PREFIX + userId);
  } catch {
    /* storage blocked: nothing was kept */
  }
}
