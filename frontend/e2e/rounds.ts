import type { Page } from "./fixtures";

/**
 * The live round's "… QUESTION n OF m" line, or null when no round is on screen. It never waits.
 *
 * The round ends, and the line disappears, the moment the last answer is saved. A waiting read
 * (`innerText()`) that starts just before then waits for a line that never comes back, so a check
 * like "is the round still on screen? then has its question changed?" hung until the test's
 * timeout. That is how e2e/formats.spec.ts timed out "waiting on the predicate" after
 * "Finish interview", although the results had loaded in milliseconds.
 */
export async function roundPosition(page: Page): Promise<string | null> {
  const [line] = await page.locator(".round__bar .eyebrow").allInnerTexts();
  return line ?? null;
}
