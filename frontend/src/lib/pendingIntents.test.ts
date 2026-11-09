/**
 * The unresolved-action record (Volume 8, prompt 1): one key per intent across tabs and reloads,
 * changed content is a new intent, per account, bounded, expiring, and honest when storage fails.
 */
import { findIntent, fingerprint, forgetAllIntents, forgetIntent, INTENT_TTL_MS, keyForIntent } from "./pendingIntents";

const ADA = "user-ada";
const BEA = "user-bea";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

it("the same intent gets the same key, from any tab or after a reload; changed content gets a new one", () => {
  const print = fingerprint("two-sum", "submit", "class A {}");
  const first = keyForIntent(ADA, "submission", "two-sum", print);
  const again = keyForIntent(ADA, "submission", "two-sum", print); // another tab, or after a reload
  expect(first.kept).toBe(true);
  expect(again.key).toBe(first.key);
  const changed = keyForIntent(ADA, "submission", "two-sum", fingerprint("two-sum", "submit", "class B {}"));
  expect(changed.key).not.toBe(first.key);
  expect(findIntent(ADA, "submission", "two-sum")?.key).toBe(changed.key);
});

it("keeps no content: only kind, target, key, a fingerprint and a time", () => {
  keyForIntent(ADA, "story", "new", fingerprint(JSON.stringify({ title: "PRIVATE-STORY-TEXT" })));
  const raw = localStorage.getItem(`codecoach.pending.v1.${ADA}`) ?? "";
  expect(raw).not.toContain("PRIVATE-STORY-TEXT");
  expect(Object.keys(JSON.parse(raw)["story:new"]).sort()).toEqual(["fingerprint", "key", "kind", "sentAt", "target", "v"]);
});

it("is per account: another account never sees it, and a deliberate sign-out removes it", () => {
  keyForIntent(ADA, "hint", "two-sum", fingerprint("two-sum", 1));
  expect(findIntent(BEA, "hint", "two-sum")).toBeNull();
  expect(findIntent(ADA, "hint", "two-sum")).not.toBeNull();
  forgetAllIntents(ADA);
  expect(findIntent(ADA, "hint", "two-sum")).toBeNull();
});

it("forgets only the key it was told about, expires after a day, and keeps at most 20", () => {
  const { key } = keyForIntent(ADA, "review", "two-sum", fingerprint("x"));
  forgetIntent(ADA, "review", "two-sum", "some-other-key");
  expect(findIntent(ADA, "review", "two-sum")?.key).toBe(key);
  forgetIntent(ADA, "review", "two-sum", key);
  expect(findIntent(ADA, "review", "two-sum")).toBeNull();

  keyForIntent(ADA, "submission", "old", fingerprint("old"));
  const store = JSON.parse(localStorage.getItem(`codecoach.pending.v1.${ADA}`)!);
  store["submission:old"].sentAt = Date.now() - INTENT_TTL_MS - 1;
  localStorage.setItem(`codecoach.pending.v1.${ADA}`, JSON.stringify(store));
  expect(findIntent(ADA, "submission", "old")).toBeNull();

  for (let i = 0; i < 25; i++) keyForIntent(ADA, "submission", `p${i}`, fingerprint(i));
  expect(Object.keys(JSON.parse(localStorage.getItem(`codecoach.pending.v1.${ADA}`)!))).toHaveLength(20);
});

it("says when this browser couldn't keep the record, and still gives a key for this page", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
  const result = keyForIntent(ADA, "submission", "two-sum", fingerprint("x"));
  expect(result.kept).toBe(false);
  expect(result.key).toMatch(/^[0-9a-f-]{16,}$/);
  expect(findIntent(ADA, "submission", "two-sum")).toBeNull();
});
