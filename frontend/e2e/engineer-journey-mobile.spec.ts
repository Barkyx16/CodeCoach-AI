import { expect, test } from "./fixtures";
import {
  BASELINE, JUDGE_NEEDED, PROBLEM, RESUBMISSION, SE_TRACK, expectResultShown, judgeReady, paste, submitAndJudge, verdict,
} from "./engineer-journey";
import { Recorder, api, newAccount, signIn } from "./preparation-journey";

/**
 * The software engineer's journey at phone size (the mobile project: Pixel 7), for the steps that
 * have a phone layout of their own: the coding workspace's Problem, Code and Coach tabs (a hint
 * checked then asked for, a baseline and a resubmission judged in the sandbox, an approved code
 * review) and the submission's recorded help. The other steps' pages are the desktop ones in one
 * column, and are checked at phone width by their own specs. Volume 13, prompt 10;
 * docs/PREPARATION_JOURNEY.md. Synthetic data.
 */
test.skip(process.env.E2E_JUDGE !== "1", `This journey ${JUDGE_NEEDED}.`);

test("the software engineer's judged steps at phone size", async ({ page, context, request }, info) => {
  test.setTimeout(300_000);
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const rec = new Recorder(info, "engineer-journey-mobile");
  try {
    const acct = await newAccount(request, "engineer-phone", SE_TRACK);
    await rec.step("The judge is ready", async (check) => {
      await judgeReady(request, acct, rec);
      check("/capabilities: code execution on and the judge ready");
    });
    await signIn(page, acct.email);
    const tab = (name: string) => page.getByRole("tab", { name, exact: true });
    let baselineId = "";

    await rec.step("Approved coach context: a hint, in the Coach tab", async (check) => {
      await page.goto(`/problems/${PROBLEM}`);
      await tab("Code").click();
      await expect(page.locator(".monaco-editor")).toBeVisible();
      await paste(page, BASELINE);
      await tab("Coach").click();
      const coach = page.getByRole("region", { name: "AI coach" });
      await coach.getByRole("button", { name: "Get a hint" }).click();
      const panel = coach.locator("section").filter({ has: page.getByRole("heading", { name: "What the coach will read" }) });
      await expect(panel.getByLabel("Exactly what's sent: Your code")).toContainText("return new int[] {0, 1};");
      await panel.getByRole("button", { name: "Ask for the level 1 hint" }).click();
      await expect(coach.getByText("Level 1 · Nudge")).toBeVisible();
      check("the Coach tab shows what the hint will read, then the level 1 hint");
    }, ["built-in coach"]);

    await rec.step("A coding baseline, judged for real, in the Code tab", async (check) => {
      await tab("Code").click();
      const { sub, seenMs } = await submitAndJudge(page, request, acct, "Some tests failed. Check the cases below.");
      expect(sub.status).toBe("FAILED");
      await expectResultShown(page, sub);
      baselineId = sub.id;
      rec.ids.baseline_submission = sub.id;
      rec.judged.push(verdict("A coding baseline, judged for real, in the Code tab", sub, seenMs));
      check(`judged in the sandbox: ${sub.status}, ${sub.result!.passed_count}/${sub.result!.total_count}, shown under the editor`);
    }, ["real judge"]);

    await rec.step("An approved code review, in the Coach tab", async (check) => {
      await tab("Coach").click();
      await page.getByRole("tab", { name: "Code review" }).click();
      await page.getByRole("button", { name: "Review my code" }).click();
      const panel = page.locator("section").filter({ has: page.getByRole("heading", { name: "What the coach will read" }) });
      await expect(panel.getByLabel("Exactly what's sent: Your code")).toContainText("return new int[] {0, 1};");
      const sending = page.waitForRequest((r) => new URL(r.url()).pathname === "/api/v1/ai/review" && r.method() === "POST");
      await panel.getByRole("button", { name: "Send for review" }).click();
      expect(((await sending).postDataJSON() as { source_code: string }).source_code).toBe(BASELINE);
      await expect(page.getByText("What's working")).toBeVisible();
      check("the review shows what it will read, sends that code, and the built-in coach answers");
    }, ["built-in coach"]);

    await rec.step("Its recorded help", async (check) => {
      await page.goto(`/history/submissions/${baselineId}`);
      await expect(page.locator(".attempt-conditions")).toContainText("In-app help before this attempt: Hint shown");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      check(`"Hint shown" on the baseline, with no sideways scroll at phone width`);
    });

    await rec.step("A resubmission, judged for real, in the Code tab", async (check) => {
      await page.goto(`/problems/${PROBLEM}`);
      await tab("Code").click();
      await expect(page.locator(".monaco-editor")).toBeVisible();
      await paste(page, RESUBMISSION);
      const { sub, seenMs } = await submitAndJudge(page, request, acct, "All tests passed. Nice work.");
      expect(sub.status).toBe("PASSED");
      await expectResultShown(page, sub);
      expect(sub.conditions?.labels).toEqual(["No in-app help recorded"]);
      rec.ids.resubmission = sub.id;
      rec.judged.push(verdict("A resubmission, judged for real, in the Code tab", sub, seenMs));
      const subs = await api<{ items: { id: string }[] } | { id: string }[]>(request, acct.auth, "get", "/api/v1/me/submissions");
      const ids = (Array.isArray(subs) ? subs : subs.items).map((s) => s.id);
      expect(ids).toEqual(expect.arrayContaining([baselineId, sub.id]));
      check(`judged in the sandbox: ${sub.status}, ${sub.result!.passed_count}/${sub.result!.total_count}, with its own help ("No in-app help recorded")`);
    }, ["real judge"]);
  } finally {
    rec.write(true);
  }
});
