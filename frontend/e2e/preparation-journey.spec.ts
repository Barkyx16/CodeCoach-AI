import { test } from "./fixtures";
import { journey } from "./preparation-journey";

/**
 * One connected preparation journey on desktop (Volume 12, prompt 10; docs/PREPARATION_JOURNEY.md):
 * see e2e/preparation-journey.ts for the steps. The branches are in preparation-branches.spec.ts;
 * the same journey at phone size is preparation-journey-mobile.spec.ts. Synthetic data.
 */
test("a target requirement becomes a baseline, an accepted improvement on the calendar, a follow-up and a kit", async ({ page, context, browser, request }, info) => {
  test.setTimeout(240_000);
  await journey(page, context, browser, request, info);
});
