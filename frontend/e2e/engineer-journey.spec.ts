import { test } from "./fixtures";
import { JUDGE_NEEDED, engineerJourney } from "./engineer-journey";

/**
 * A software engineer's preparation journey on desktop, with the real judge in its gVisor sandbox
 * and the built-in coach (Volume 13, prompt 10; docs/PREPARATION_JOURNEY.md): see
 * e2e/engineer-journey.ts for the steps. Its branches are engineer-branches.spec.ts; the steps that
 * have a phone layout run at phone size in engineer-journey-mobile.spec.ts. CI's sandbox job runs
 * all three twice (`--repeat-each=2`). Synthetic data.
 */
test.skip(process.env.E2E_JUDGE !== "1", `This journey ${JUDGE_NEEDED}.`);

test("a target requirement becomes a judged baseline, an approved review, an accepted improvement on the calendar, a judged resubmission and a kit", async ({ page, context, browser, request }, info) => {
  test.setTimeout(360_000);
  await engineerJourney(page, context, browser, request, info);
});
