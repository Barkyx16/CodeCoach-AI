/** The stored shortcut list (docs/SHORTCUTS.md): ids from a fixed set only, at most eight, no repeats. */
import { DEFAULT_SHORTCUTS, SHORTCUTS_LIMIT, parseShortcuts, saveShortcuts, shortcutCatalog, shortcutsKey } from "./shortcuts";

const ids = ["library", "notes", "stories", "applications", "plan", "goals", "analytics", "history", "targets", "schedule", "reflections"];

it("keeps at most eight known ids, in order, without repeats", () => {
  const parsed = parseShortcuts(JSON.stringify({ v: 1, ids: ["notes", "notes", ...ids] }));
  expect(parsed.ids).toEqual(["notes", "library", "stories", "applications", "plan", "goals", "analytics", "history"]);
  expect(parsed.ids).toHaveLength(SHORTCUTS_LIMIT);
  expect(parsed.dropped).toBe(ids.length + 2 - SHORTCUTS_LIMIT);
  expect(parseShortcuts(null)).toEqual({ ids: [...DEFAULT_SHORTCUTS], custom: false, dropped: 0, unreadable: false });
  expect(parseShortcuts(JSON.stringify({ v: 2, ids: ["notes"] })).unreadable).toBe(true); // a format it doesn't know
  expect(parseShortcuts(JSON.stringify(["notes"])).unreadable).toBe(true);
});

it("writes only known ids, and nothing else about the page", () => {
  expect(saveShortcuts("u-9", ["notes", "https://evil.example", "triage", "notes", ...ids])).toBe(true);
  const raw = window.localStorage.getItem(shortcutsKey("u-9"))!;
  expect(JSON.parse(raw)).toEqual({ v: 1, ids: ["notes", "library", "stories", "applications", "plan", "goals", "analytics", "history"] });
  expect(raw).not.toMatch(/\//); // no paths or URLs, only ids
});

it("offers the career's own library and none of the excluded pages", () => {
  const coding = shortcutCatalog({ coding: true, executionEnabled: true, demoMode: false });
  const nurse = shortcutCatalog({ coding: false, executionEnabled: true, demoMode: false });
  expect(coding.find((s) => s.id === "library")?.label).toBe("Coding problems");
  expect(nurse.find((s) => s.id === "library")?.label).toBe("Interview questions");
  expect(nurse.some((s) => s.id === "whiteboard")).toBe(false);
  for (const list of [coding, nurse]) {
    expect(list.some((s) => ["dashboard", "triage", "sign-in", "register", "demo"].includes(s.id))).toBe(false);
    expect(new Set(list.map((s) => s.id)).size).toBe(list.length);
  }
});
