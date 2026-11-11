import { type CommandContext, commandsFor } from "@/app/commands";

import type { ReleaseEntry } from "./releases";

/**
 * What's new (Volume 11, prompt 10; docs/WHATS_NEW.md): which entries this build may show, what
 * each one opens for this learner, and which ones they haven't seen.
 */

/** This build's release (release.json via vite.config.ts); 0 when it's missing, and then nothing shows. */
export const BUILD_RELEASE: number =
  typeof __CODECOACH_RELEASE__ === "number" && Number.isInteger(__CODECOACH_RELEASE__) && __CODECOACH_RELEASE__ > 0 ? __CODECOACH_RELEASE__ : 0;

const ID = /^[a-z0-9-]{1,48}$/;
const TEXT_MAX = 400;
const text = (v: unknown, required: boolean) => (v === undefined && !required) || (typeof v === "string" && v.trim().length > 0 && v.length <= TEXT_MAX);

/** Every command id the app has in some sign-in, career or server state. */
const KNOWN_COMMANDS: ReadonlySet<string> = new Set(
  [true, false].flatMap((signedIn) => [true, false].flatMap((coding) =>
    commandsFor({ signedIn, isAdmin: false, coding, executionEnabled: true, demoMode: false }).map((c) => c.id))),
);

/** A well-formed entry: known fields only as plain text, a known page, a release number. Anything
 * else (an unknown page, a URL, a missing title) means the entry isn't shown. */
export function isValidEntry(e: unknown): e is ReleaseEntry {
  if (!e || typeof e !== "object") return false;
  const x = e as Record<string, unknown>;
  return typeof x.id === "string" && ID.test(x.id)
    && typeof x.release === "number" && Number.isInteger(x.release) && x.release >= 1
    && text(x.title, true) && text(x.what, true) && text(x.where, true) && text(x.limit, false)
    && typeof x.opens === "string" && KNOWN_COMMANDS.has(x.opens)
    && (x.audience === undefined || x.audience === "coding")
    && (x.needs === undefined || x.needs === "code-runner");
}

/** The entries this build ships: well formed, with a release no later than the build's. A build
 * whose release is unknown (0) shows none. Newest release first, then in the list's order. */
export function shippedEntries(entries: readonly unknown[], buildRelease: number): ReleaseEntry[] {
  if (!Number.isInteger(buildRelease) || buildRelease < 1) return [];
  const seen = new Set<string>();
  return entries
    .filter(isValidEntry)
    .filter((e) => e.release <= buildRelease && !seen.has(e.id) && seen.add(e.id))
    .map((e, i) => ({ e, i }))
    .sort((a, b) => b.e.release - a.e.release || a.i - b.i)
    .map(({ e }) => e);
}

export type WhatsNewContext = Omit<CommandContext, "isAdmin">;

export interface EntryAccess {
  /** Where "Open" goes; absent when it can't be opened from here. */
  to?: string;
  label?: string;
  /** Why it can't be opened by this learner here. */
  unavailable?: string;
  /** Something the page will say (e.g. code isn't run on this server); it still opens. */
  note?: string;
}

/** What an entry opens for this learner, by the command palette's own rules (the router's pages,
 * the career, the server), never a guess: a page that isn't offered here gets the reason, not a link. */
export function entryAccess(entry: ReleaseEntry, context: WhatsNewContext, careerTitle?: string): EntryAccess {
  const command = commandsFor({ ...context, isAdmin: false }).find((c) => c.id === entry.opens);
  const forCareer = careerTitle ? `${careerTitle} practice` : "practice for your current career";
  if (entry.audience === "coding" && !context.coding) return { unavailable: `For careers with coding practice: not part of ${forCareer}.` };
  if (!command) return { unavailable: context.signedIn ? "Not available here." : "Sign in to use it." };
  if (command.unavailable) return { unavailable: command.unavailable };
  const note = entry.needs === "code-runner" && !context.executionEnabled
    ? "Code isn't run on this server right now: attempts are saved, not judged."
    : command.note;
  return { to: command.to, label: command.label, ...(note ? { note } : {}) };
}

/** Counts toward "new": an entry this learner's career can use (whatever the server can do today). */
export const forThisCareer = (entry: ReleaseEntry, context: Pick<WhatsNewContext, "coding">) => entry.audience !== "coding" || context.coding;

// --- What this account has seen, in this browser ---------------------------------------------------

/** `{v: 1, seen: <release>}`: the newest release this account has looked at here. Nothing else. */
export const seenKey = (userId: string) => `codecoach.whatsnew.v1.${userId}`;

export type SeenState =
  | { kind: "none" } // nothing stored: this account hasn't opened What's new in this browser
  | { kind: "seen"; release: number }
  | { kind: "unavailable" }; // this browser won't let the page read or keep it

const listeners = new Set<() => void>();
const changed = () => listeners.forEach((l) => l());

/** The raw stored value (or a marker when storage refuses), for useSyncExternalStore. */
export function readSeenRaw(userId: string): string | null {
  try {
    return window.localStorage.getItem(seenKey(userId));
  } catch {
    return "\u0000unavailable";
  }
}

export function parseSeen(raw: string | null): SeenState {
  if (raw === "\u0000unavailable") return { kind: "unavailable" };
  if (raw === null) return { kind: "none" };
  try {
    const v = JSON.parse(raw) as { v?: unknown; seen?: unknown };
    if (v && v.v === 1 && typeof v.seen === "number" && Number.isInteger(v.seen) && v.seen >= 0) return { kind: "seen", release: v.seen };
  } catch {
    /* malformed: as if nothing were stored */
  }
  return { kind: "none" };
}

/** Mark everything up to `release` as seen for this account here. False when the browser refuses. */
export function markSeen(userId: string, release: number): boolean {
  try {
    window.localStorage.setItem(seenKey(userId), JSON.stringify({ v: 1, seen: release }));
  } catch {
    return false;
  }
  changed();
  return true;
}

/** Same-tab changes (this module) and other tabs' (the storage event). */
export function subscribeSeen(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

/** The newest release counted as seen. Nothing stored: everything before this build's own release,
 * so a first look shows this release's changes as new and the older ones as earlier changes. */
export function seenRelease(state: SeenState, buildRelease: number): number | null {
  if (state.kind === "unavailable") return null; // can't tell: nothing is marked new
  if (state.kind === "seen") return state.release;
  return buildRelease - 1;
}

/** Entries newer than what's been seen, for this career. None when that can't be known. */
export function unseenEntries(entries: ReleaseEntry[], seen: number | null, context: Pick<WhatsNewContext, "coding">): ReleaseEntry[] {
  if (seen === null) return [];
  return entries.filter((e) => e.release > seen && forThisCareer(e, context));
}
