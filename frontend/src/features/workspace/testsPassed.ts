/**
 * A judged result's counts in the one set of words every list of submissions uses: "6 of 8 tests
 * passed (hidden 4 of 5)". A submission's own comparison and a target requirement's list say them
 * the same way (Volume 17, prompt 10; docs/COMPARING_ATTEMPTS.md, "Under a target's requirement").
 */
export function testsPassedWords(passed?: number | null, total?: number | null, hiddenPassed?: number | null, hiddenTotal?: number | null): string | null {
  if (passed == null || total == null) return null;
  return `${passed} of ${total} tests passed${hiddenTotal ? ` (hidden ${hiddenPassed ?? 0} of ${hiddenTotal})` : ""}`;
}
