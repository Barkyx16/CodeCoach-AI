/**
 * Copies removed on purpose stay removed (Volume 10, prompt 10; docs/YOUR_DATA.md): a page that had
 * the copy open, here or in another tab, can't write it back (an autosave timer, an effect after a
 * refetch, a flush on hide); a page opened afterwards keeps a new one; removal touches only the
 * keys given; sign-out forgets which were removed but the counter only grows; and every draft
 * writer in the app goes through this module.
 */
import { act, renderHook } from "@testing-library/react";

import { clearLocalWork, COPY_PREFIXES } from "@/auth/localWork";
import { KIND_DETAILS } from "@/features/privacy/copyKinds";
import { useDraft } from "@/features/workspace/useDraft";
import { useStoredDraft } from "@/hooks/useStoredDraft";

import { REMOVALS_KEY, dropCopy, forgetRemovals, removalMark, removeCopies, removedSince, writeCopy } from "./deviceCopies";

const A = "codecoach.answer.u-1.registered-nurse.q1";
const B = "story-draft:u-1:s1";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

it("refuses to write back a copy removed after the page opened it, and lets a page opened later keep one", () => {
  const before = removalMark();
  expect(writeCopy(A, "first", before)).toBe(true);
  localStorage.setItem(B, "story");
  localStorage.setItem("codecoach.display.v1", "{}");
  const result = removeCopies([A]);
  expect(result).toEqual({ removed: [A], failed: [], guarded: true });
  expect(localStorage.getItem(B)).toBe("story"); // only the key given
  expect(localStorage.getItem("codecoach.display.v1")).toBe("{}");
  expect(writeCopy(A, "first, again", before)).toBe(false);
  expect(localStorage.getItem(A)).toBeNull();
  expect(writeCopy(B, "other copies are unaffected", before)).toBe(true);
  const after = removalMark();
  expect(after).toBeGreaterThan(before);
  expect(writeCopy(A, "a new copy", after)).toBe(true);
  dropCopy(A);
  expect(localStorage.getItem(A)).toBeNull();
});

it("records only keys, numbers and times, keeps the counter through sign-out, and says when it couldn't record", () => {
  localStorage.setItem(A, "PRIVATE text");
  removeCopies([A], 1_000);
  const stored = localStorage.getItem(REMOVALS_KEY)!;
  expect(stored).not.toContain("PRIVATE");
  expect(JSON.parse(stored)).toEqual({ seq: 1, removed: { [A]: { seq: 1, at: 1_000 } } });
  clearLocalWork("u-1"); // sign-out
  expect(JSON.parse(localStorage.getItem(REMOVALS_KEY)!)).toEqual({ seq: 1, removed: {} });
  expect(removalMark()).toBe(1); // an old page's mark can't look newer than the next removal
  forgetRemovals();
  removeCopies([B]);
  expect(removedSince(B, 1)).toBe(true);

  const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
  localStorage.removeItem(A);
  expect(removeCopies([A]).guarded).toBe(false);
  expect(writeCopy(A, "x", removalMark())).toBe(false); // the browser refused: said, not thrown
  setItem.mockRestore();
});

it("a text draft open in another tab doesn't come back from more typing; reopening keeps a new one", () => {
  const first = renderHook(() => useStoredDraft(A));
  act(() => first.result.current[1]("I checked"));
  expect(localStorage.getItem(A)).toBe("I checked");
  removeCopies([A]); // "Your data", in another tab
  act(() => first.result.current[1]("I checked the chart"));
  expect(localStorage.getItem(A)).toBeNull();
  expect(first.result.current[0]).toBe("I checked the chart"); // still on the page
  expect(first.result.current[2]).toBe(false); // and the page says it isn't kept
  first.unmount();
  const reopened = renderHook(() => useStoredDraft(A));
  expect(reopened.result.current[0]).toBe("");
  act(() => reopened.result.current[1]("A new answer"));
  expect(localStorage.getItem(A)).toBe("A new answer");
});

it("code waiting for its autosave when the copy is removed isn't saved by the timer or by leaving", () => {
  vi.useFakeTimers();
  const key = "codecoach.draft.v1.u-1.two-sum";
  const editor = renderHook(() => useDraft("two-sum", "starter", "u-1", 600));
  act(() => editor.result.current.setCode("class A {}"));
  removeCopies([key]); // before the timer fires
  act(() => { vi.advanceTimersByTime(700); });
  expect(localStorage.getItem(key)).toBeNull();
  expect(editor.result.current.saveState).toBe("error");
  act(() => { window.dispatchEvent(new Event("pagehide")); });
  editor.unmount(); // leaving flushes, and still doesn't put it back
  expect(localStorage.getItem(key)).toBeNull();
});

it("every kind of copy sign-out clears is described on Your data, and nothing else is", () => {
  expect(Object.keys(KIND_DETAILS).sort()).toEqual(COPY_PREFIXES.map((p) => p.id).sort());
});

it("every file that writes to this browser's storage directly is a known one (drafts go through writeCopy)", () => {
  const sources = import.meta.glob(["/src/**/*.{ts,tsx}", "!/src/**/*.test.{ts,tsx}", "!/src/test/**"], {
    query: "?raw", import: "default", eager: true,
  }) as Record<string, string>;
  const writers = Object.entries(sources)
    .filter(([, text]) => /localStorage\.setItem\(|\bstorage\.set\(/.test(text))
    .map(([path]) => path.replace(/^\/src\//, ""))
    .sort();
  // Each writes settings, sign-in markers, pending-action records or this module's own state;
  // none writes a learner's unsent text.
  expect(writers).toEqual([
    "app/SessionEndedBanner.tsx", // a probe: can this browser store anything?
    "app/commands.ts", // recently opened pages (names only), listed on "Your data"
    "auth/deviceUser.ts", // which account last used this device
    "auth/emailVerified.ts", // where to go after verifying
    "auth/pendingSignOut.ts", // a sign-out to finish
    "features/careers/QuestionPage.tsx", // the "reflect first" setting; the answer itself uses useStoredDraft
    "features/dashboard/ContinueCard.tsx", // whether "Continue your work" is hidden on this device
    "features/display/DisplayProvider.tsx", // display settings
    "features/drills/DrillPage.tsx", // the delivery setting; the answer itself uses useStoredDraft
    "features/onboarding/finishIntent.ts", // a tour step to finish
    "features/plan/PlanChanges.tsx", // the plan version last seen
    "features/plan/todayMinutes.ts", // minutes set for today
    "features/settings/EditorPreferencesProvider.tsx", // editor settings
    "features/voice/voicePrefs.ts", // voice settings
    "lib/deviceCopies.ts",
    "lib/pendingIntents.ts",
    "lib/storage.ts",
  ]);
});
