import { expect, test } from "./fixtures";
import { api, newAccount, signIn } from "./preparation-journey";

/**
 * The conditions of a drill and a scenario run (Volume 14, prompt 4; docs/ATTEMPT_CONDITIONS.md)
 * against the real API: a Learn lesson that prepares them, read first, is "Hint shown" on the
 * first attempt after it only; the next says "No in-app help recorded", and the drill's comparison
 * says the help differed. Synthetic data only.
 */
const ANSWER = "When two patients needed me at once I checked the one short of breath first, asked a colleague to tell the other I was coming, then gave the medicine and documented both.";

test("a lesson read first is the help before the next drill and scenario attempt, and only that one", async ({ page, request }) => {
  const acct = await newAccount(request, "practice-conditions", "registered-nurse");
  for (const unit of ["rn-star-answers", "rn-prioritization"]) {
    await api(request, acct.auth, "post", `/api/v1/me/learn/units/${unit}/events`, { kind: "read", version: 1 });
  }
  await signIn(page, acct.email);

  // A drill: the lesson shows on the first attempt, not the second, and the comparison says so.
  await page.goto("/drills/example");
  const box = page.getByLabel(/Answer \(check and edit/);
  await box.fill(ANSWER);
  await page.getByRole("button", { name: "Get feedback" }).click();
  let fb = page.getByRole("region", { name: /Feedback on your attempt/ });
  await expect(fb.locator(".attempt-conditions")).toContainText("In-app help before this attempt: Hint shown");
  await expect(fb.locator(".attempt-conditions")).toContainText("Lesson “Structuring a behavioral answer with STAR” read");
  await box.fill(`${ANSWER} It went well.`);
  await page.getByRole("button", { name: "Get feedback" }).click();
  fb = page.getByRole("region", { name: /Feedback on your attempt/ });
  await expect(fb.locator(".attempt-conditions")).toContainText("In-app help before this attempt: No in-app help recorded");
  await expect(fb).toContainText("The in-app help differed: before the earlier one, hint shown; before this one, none recorded.");
  await expect(page.locator(".drill-history")).toContainText("In-app help: Hint shown");

  // A scenario: the run started after the lesson says so; its row in your attempts too.
  await page.goto("/scenarios/rn-two-patients");
  await page.getByRole("button", { name: "Start the scenario" }).click();
  await expect(page).toHaveURL(/\/scenarios\/attempts\//);
  await expect(page.locator(".attempt-conditions")).toContainText("In-app help before this attempt: Hint shown");
  await expect(page.locator(".attempt-conditions")).toContainText("Lesson “Prioritizing when several patients need you” read");
  await page.goto("/scenarios/rn-two-patients");
  await expect(page.getByRole("heading", { name: "Your attempts" }).locator("..")).toContainText("In-app help: Hint shown");
});
