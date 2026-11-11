import { type Command, type CommandContext, commandsFor } from "@/app/commands";
import { storage } from "@/lib/storage";

/**
 * Home shortcuts (Volume 11, prompt 2; docs/SHORTCUTS.md): a short list of pages the learner keeps
 * one click away on the dashboard. The choices are the command palette's own commands (the
 * router's real pages, with their real labels and the same career and server rules), minus the
 * dashboard itself, admin tools and signed-out pages. A shortcut only opens a page: none submits,
 * records, deletes or spends anything, and choosing or arranging them changes nothing on the
 * account.
 *
 * Kept in this browser, per account: `codecoach.shortcuts.v1.<user id>` holds `{v: 1, ids}` and
 * nothing else: page ids from a fixed set, never a URL, a record's title or anything typed. No list
 * stored means the defaults. Stored ids are checked when read: an id the app doesn't offer any more
 * (or never did) is left out and counted, at most SHORTCUTS_LIMIT are kept, and one that's offered
 * only to some careers stays in the list, shown as not available for this career, until removed.
 */

export const SHORTCUTS_LIMIT = 8;
export const DEFAULT_SHORTCUTS: readonly string[] = ["library", "notes", "stories", "applications", "plan"];
export const shortcutsKey = (userId: string) => `codecoach.shortcuts.v1.${userId}`;

/** Never offered: the page they'd sit on, admin tools (a home page isn't the place, and access is
 * decided by the server anyway) and pages for people who aren't signed in. */
const EXCLUDED = new Set(["dashboard", "triage", "sign-in", "register", "demo"]);
/** The practice library is one shortcut whatever it's called for the career ("Coding problems",
 * "Interview questions"): both commands open /problems. */
const LIBRARY = new Set(["problems", "questions"]);
const ID = /^[a-z-]{1,40}$/;

export const shortcutId = (c: Command) => (LIBRARY.has(c.id) ? "library" : c.id);

export interface Shortcut {
  id: string;
  label: string;
  detail: string;
  section: Command["section"];
  to: string;
  /** Something the page will say (e.g. code isn't run on this server); it still opens. */
  note?: string;
  /** Why it can't be opened right now; it isn't a link. */
  unavailable?: string;
}

const signedInContext = (c: Omit<CommandContext, "signedIn" | "isAdmin">): CommandContext => ({ ...c, signedIn: true, isAdmin: false });

/** Every shortcut id the app offers in some career or server state, with its label there. */
const EVERY: ReadonlyMap<string, Command> = new Map(
  [true, false].flatMap((coding) => commandsFor(signedInContext({ coding, executionEnabled: true, demoMode: false })))
    .filter((c) => !EXCLUDED.has(shortcutId(c)))
    .map((c) => [shortcutId(c), c] as const),
);

export const isKnownShortcut = (id: unknown): id is string => typeof id === "string" && ID.test(id) && EVERY.has(id);

/** What can be a shortcut for this learner right now, in the palette's order. */
export function shortcutCatalog(context: Omit<CommandContext, "signedIn" | "isAdmin">): Shortcut[] {
  return commandsFor(signedInContext(context))
    .filter((c) => !EXCLUDED.has(shortcutId(c)))
    .map((c) => ({ id: shortcutId(c), label: c.label, detail: c.detail, section: c.section, to: c.to, note: c.note, unavailable: c.unavailable }));
}

/** The stored ids as shortcuts: offered ones as they are now, career-only ones as unavailable. */
export function resolveShortcuts(ids: readonly string[], catalog: Shortcut[], careerTitle?: string): Shortcut[] {
  const offered = new Map(catalog.map((s) => [s.id, s]));
  return ids.flatMap((id) => {
    const now = offered.get(id);
    if (now) return [now];
    const known = EVERY.get(id);
    if (!known) return [];
    return [{ id, label: known.label, detail: known.detail, section: known.section, to: known.to,
      unavailable: `Not part of ${careerTitle ? `${careerTitle} practice` : "practice for your current career"}.` }];
  });
}

export interface StoredShortcuts {
  ids: string[];
  /** True when the learner saved a list; false means the defaults are shown. */
  custom: boolean;
  /** Stored entries left out: no longer offered, repeated, malformed or over the limit. */
  dropped: number;
  /** Something was stored but couldn't be read as a list at all. */
  unreadable: boolean;
}

export function parseShortcuts(raw: string | null): StoredShortcuts {
  const defaults = { ids: [...DEFAULT_SHORTCUTS], custom: false, dropped: 0, unreadable: false };
  if (raw === null) return defaults;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return { ...defaults, unreadable: true };
  }
  const list = value && typeof value === "object" && (value as { v?: unknown }).v === 1 ? (value as { ids?: unknown }).ids : undefined;
  if (!Array.isArray(list)) return { ...defaults, unreadable: true };
  const ids: string[] = [];
  for (const id of list) if (isKnownShortcut(id) && !ids.includes(id) && ids.length < SHORTCUTS_LIMIT) ids.push(id);
  return { ids, custom: true, dropped: list.length - ids.length, unreadable: false };
}

export function readShortcuts(userId: string): StoredShortcuts {
  return parseShortcuts(storage.get(shortcutsKey(userId)));
}

/** Keeps the list in this browser; false when the browser refused (nothing was kept). Only known
 * ids are ever written. */
export function saveShortcuts(userId: string, ids: readonly string[]): boolean {
  const clean = ids.filter(isKnownShortcut).filter((id, i, all) => all.indexOf(id) === i).slice(0, SHORTCUTS_LIMIT);
  return storage.set(shortcutsKey(userId), JSON.stringify({ v: 1, ids: clean }));
}

/** Back to the defaults: the stored list is removed. False when the browser refused. */
export function resetShortcuts(userId: string): boolean {
  return storage.remove(shortcutsKey(userId));
}

export const sameList = (a: readonly string[], b: readonly string[]) => a.length === b.length && a.every((x, i) => x === b[i]);
