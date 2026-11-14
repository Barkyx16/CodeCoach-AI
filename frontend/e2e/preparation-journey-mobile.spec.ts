import { test } from "./fixtures";
import { journey } from "./preparation-journey";

/** The same preparation journey at phone size (the mobile project: Pixel 7). See
 * e2e/preparation-journey.ts and docs/PREPARATION_JOURNEY.md. Synthetic data. */
test("the preparation journey at phone size", async ({ page, context, browser, request }, info) => {
  test.setTimeout(240_000);
  await journey(page, context, browser, request, info);
});
