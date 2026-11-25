import { deviceJourney } from "./device-journey";
import { test } from "./fixtures";

/**
 * One account on a desktop window and a phone-sized one, then through a version 2 backup and a
 * restore (Volume 15, prompt 10; docs/PREPARATION_JOURNEY.md, "Two devices and a restore"). See
 * e2e/device-journey.ts for the steps. Synthetic data.
 */
test("a collection, a dismissal, an improvement and answers follow the account across two devices and a restore", async ({ page, browser, request }, info) => {
  test.setTimeout(300_000);
  await deviceJourney(page, browser, request, info);
});
