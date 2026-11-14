/**
 * What's new's rules (Volume 11, prompt 10; docs/WHATS_NEW.md): only shipped, well-formed entries
 * at or before the build's release; what each opens by the palette's real rules; what's been seen,
 * per account, with storage that refuses.
 */
import { matchRoutes } from "react-router-dom";

import { commandsFor } from "@/app/commands";
import { routes } from "@/app/router";

import { ENTRIES, RELEASES, type ReleaseEntry } from "./releases";
import {
  BUILD_RELEASE, entryAccess, isValidEntry, markSeen, parseSeen, readSeenRaw, seenKey, seenRelease, shippedEntries, unseenEntries,
} from "./whatsNew";

const entry = (over: Partial<ReleaseEntry> & Record<string, unknown> = {}): ReleaseEntry =>
  ({ id: "e", release: 1, title: "A change", what: "What got better.", where: "Somewhere.", opens: "packet", ...over }) as ReleaseEntry;
const signedIn = { signedIn: true, coding: true, executionEnabled: true, demoMode: false };

describe("The curated entries", () => {
  it("are all well formed, each id once, each release named, and each opens one of the router's real pages", () => {
    expect(ENTRIES.map((e) => [e.id, isValidEntry(e)] as const).filter(([, ok]) => !ok).map(([id]) => id)).toEqual([]);
    expect(new Set(ENTRIES.map((e) => e.id)).size).toBe(ENTRIES.length);
    for (const e of ENTRIES) expect(RELEASES.map((r) => r.release)).toContain(e.release);
    for (const coding of [true, false]) {
      const commands = commandsFor({ ...signedIn, coding, isAdmin: false });
      for (const e of ENTRIES) {
        const c = commands.find((x) => x.id === e.opens);
        if (!c) { expect(e.audience, `${e.id} isn't offered when coding=${coding}`).toBe("coding"); continue; }
        const matched = matchRoutes(routes, new URL(c.to, "http://x").pathname) ?? [];
        expect(matched.at(-1)?.route.path, `${e.id} -> ${c.to}`).not.toBe("*");
        expect(matched.length, `${e.id} -> ${c.to}`).toBeGreaterThan(0);
      }
    }
  });

  it("this build's release is release.json's, and it ships what's at or before it", () => {
    expect(BUILD_RELEASE).toBe(2);
    expect(shippedEntries(ENTRIES, BUILD_RELEASE).map((e) => e.id)).toEqual(
      [...ENTRIES.filter((e) => e.release === 2), ...ENTRIES.filter((e) => e.release === 1)].map((e) => e.id));
  });
});

describe("Which entries a build shows", () => {
  const list = [entry({ id: "one", release: 1 }), entry({ id: "two", release: 2 }), entry({ id: "planned", release: 3, title: "Not built yet" })];

  it("only those at or before the build's release, newest first; a build that doesn't say shows none", () => {
    expect(shippedEntries(list, 2).map((e) => e.id)).toEqual(["two", "one"]);
    expect(shippedEntries(list, 3).map((e) => e.id)).toEqual(["planned", "two", "one"]);
    expect(shippedEntries(list, 1).map((e) => e.id)).toEqual(["one"]);
    for (const missing of [0, -1, NaN, 1.5]) expect(shippedEntries(list, missing)).toEqual([]);
  });

  it("drops a malformed entry: an unknown page, a URL or path instead of a page, missing or overlong text, odd fields; a repeated id once", () => {
    const bad = [
      entry({ id: "unknown-page", opens: "nowhere" }),
      entry({ id: "script-url", opens: "javascript:alert(1)" }),
      entry({ id: "outside", opens: "https://example.com/" }),
      entry({ id: "path", opens: "/packet" }),
      entry({ id: "no-title", title: "" }),
      entry({ id: "blank-what", what: "   " }),
      entry({ id: "too-long", what: "x".repeat(401) }),
      entry({ id: "Bad Id" }),
      entry({ id: "audience", audience: "everyone" as never }),
      entry({ id: "needs", needs: "magic" as never }),
      entry({ id: "release-zero", release: 0 }),
      entry({ id: "release-text", release: "2" as never }),
      null, "an entry", 42,
    ];
    expect(shippedEntries(bad, 9)).toEqual([]);
    expect(shippedEntries([entry({ id: "same" }), entry({ id: "same", title: "Second" })], 9).map((e) => e.title)).toEqual(["A change"]);
  });
});

describe("What an entry opens for this learner", () => {
  const lab = entry({ id: "lab", opens: "debugging", audience: "coding", needs: "code-runner" });

  it("a coding-only change: a link for a coding career, the reason for another", () => {
    expect(entryAccess(lab, signedIn)).toEqual({ to: "/problems?view=debugging", label: "Debugging lab" });
    expect(entryAccess(lab, { ...signedIn, coding: false }, "Registered Nurse")).toEqual({ unavailable: "For careers with coding practice: not part of Registered Nurse practice." });
  });

  it("a server that doesn't run code says so; signed out, a signed-in page says to sign in", () => {
    expect(entryAccess(lab, { ...signedIn, executionEnabled: false })).toEqual({
      to: "/problems?view=debugging", label: "Debugging lab", note: "Code isn't run on this server right now: attempts are saved, not judged." });
    expect(entryAccess(entry(), { ...signedIn, signedIn: false })).toEqual({ unavailable: "Sign in to use it." });
    expect(entryAccess(entry({ opens: "help" }), { ...signedIn, signedIn: false })).toEqual({ to: "/help", label: "Help" });
  });
});

describe("What's been seen", () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it("per account, one number, nothing else", () => {
    expect(parseSeen(readSeenRaw("u-1"))).toEqual({ kind: "none" });
    expect(markSeen("u-1", 2)).toBe(true);
    expect(JSON.parse(window.localStorage.getItem(seenKey("u-1"))!)).toEqual({ v: 1, seen: 2 });
    expect(parseSeen(readSeenRaw("u-1"))).toEqual({ kind: "seen", release: 2 });
    expect(parseSeen(readSeenRaw("u-2"))).toEqual({ kind: "none" }); // another account's is its own
  });

  it("a malformed value counts as nothing stored", () => {
    for (const raw of ["{", "[]", "null", '{"v":2,"seen":1}', '{"v":1,"seen":-1}', '{"v":1,"seen":"2"}', '{"v":1,"seen":1.5}']) {
      expect(parseSeen(raw), raw).toEqual({ kind: "none" });
    }
  });

  it("storage that refuses: nothing is marked new, and nothing breaks", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new DOMException("denied", "SecurityError"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
    const state = parseSeen(readSeenRaw("u-1"));
    expect(state).toEqual({ kind: "unavailable" });
    expect(seenRelease(state, 2)).toBeNull();
    expect(unseenEntries(ENTRIES, seenRelease(state, 2), { coding: true })).toEqual([]);
    expect(markSeen("u-1", 2)).toBe(false);
  });

  it("nothing stored: this release's changes are new and the earlier ones aren't; coding-only ones only for coding careers", () => {
    const shipped = shippedEntries(ENTRIES, 2);
    expect(seenRelease({ kind: "none" }, 2)).toBe(1);
    expect(unseenEntries(shipped, 1, { coding: false }).map((e) => e.release)).toEqual(ENTRIES.filter((e) => e.release === 2).map(() => 2));
    expect(unseenEntries(shipped, 0, { coding: false }).some((e) => e.audience === "coding")).toBe(false);
    expect(unseenEntries(shipped, 0, { coding: true }).some((e) => e.audience === "coding")).toBe(true);
    expect(unseenEntries(shipped, 2, { coding: true })).toEqual([]);
    expect(unseenEntries(shipped, 5, { coding: true })).toEqual([]); // seen by a newer build: nothing new here
  });
});
