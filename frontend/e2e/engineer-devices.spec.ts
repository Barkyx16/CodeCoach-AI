import { test } from "./fixtures";
import { engineerDevices } from "./engineer-devices";
import { JUDGE_NEEDED } from "./engineer-journey";

/**
 * One engineer on two devices, judged for real (Volume 16, prompt 10; docs/PREPARATION_JOURNEY.md,
 * "An engineer on two devices"): see e2e/engineer-devices.ts for the steps. It needs the real judge
 * (E2E_JUDGE=1); CI's sandbox job runs it twice on fresh accounts with the engineer's other specs
 * and keeps the record. Synthetic data.
 */
test.skip(process.env.E2E_JUDGE !== "1", `This journey ${JUDGE_NEEDED}.`);

test("an engineer's judged code, a checked interview and the plan follow the account from a desktop to a phone", async ({ page, context, browser, request }, info) => {
  test.setTimeout(480_000);
  await engineerDevices(page, context, browser, request, info);
});
