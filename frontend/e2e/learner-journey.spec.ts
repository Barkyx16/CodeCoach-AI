import { expect, test, type Page } from "./fixtures";

// The learner journey against the real backend (Learner Experience pack): a new nurse starts from
// the dashboard's Up next, answers, sees what the try covered, revises it for one missing point,
// sees the two tries compared, survives a dropped send without saving twice, and the page stays
// usable at 320px. Synthetic account and answers only.

const THIN = "I check the patient carefully and talk with the team about what I find. I write it all down and ask for help when " +
  "I need it. I stay calm, follow the policy, make sure the patient is comfortable and safe, and explain what is happening " +
  "to them and their family in a clear and kind way.";
const RESULT = " Last winter this meant I caught a falling oxygen level early; within the hour it was back to 96% and the patient stayed on the ward.";

const fits = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);

test("first use to a revised, compared answer, with a dropped send and a 320px screen", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`journey-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();

  // First use: Up next says how it chooses, and starts on the easy level.
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText(/Picked from your own answers by a fixed rule/)).toContainText("You're on Easy (0 of 10 answered");
  const upNext = page.locator(".rec-list").first().getByRole("link").first();
  const title = (await upNext.locator("strong").innerText()).trim();
  await upNext.click();
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();

  // A dropped send: the request never reaches the server, so nothing is saved, the text stays,
  // and the page says the outcome is unknown instead of inviting a blind resend.
  const box = page.getByRole("textbox", { name: "Your answer" });
  await box.fill(THIN);
  await page.route("**/api/v1/careers/*/questions/*/answers", (route) =>
    route.request().method() === "POST" ? route.abort("connectionreset") : route.continue());
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByText(/isn't certain whether this answer was saved/)).toBeVisible();
  await expect(box).toHaveValue(THIN);
  await page.unroute("**/api/v1/careers/*/questions/*/answers");

  // Sent for real: feedback, then what this try covered and one way on.
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: "Feedback", exact: true })).toBeVisible();
  const recap = page.getByRole("region", { name: "What next" });
  await expect(recap).toContainText(/covered \d of \d points the rubric looks for/);
  await expect(page.getByRole("button", { name: /^Try 1 \(first\)/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Try 2/ })).toHaveCount(0); // the dropped send saved nothing

  // Revise for the missing point: the box starts from try 1, which stays as it was.
  await recap.getByRole("button", { name: "Revise this answer" }).click();
  await expect(box).toHaveValue(THIN);
  await expect(box).toBeFocused();
  await expect(page.getByText(/^Revising try 1: add “/)).toBeVisible();
  await box.press("End");
  await box.pressSequentially(RESULT);
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: "Feedback", exact: true })).toBeVisible();
  // Same question version, rubric and coach: compared directly, by points, with both scores.
  await expect(recap).toContainText(/Compared with try 1 \(same question version, rubric and coach\):.*score (\d+, now \d+|\d+ both times)\./);
  await expect(page.getByRole("button", { name: /^Try 2/ })).toBeVisible();

  // Try 1 opens under its own title, from the URL, unchanged.
  await page.getByRole("button", { name: /^Try 1 \(first\)/ }).click();
  await expect(page).toHaveURL(/\?answer=/);
  await expect(page.getByRole("region", { name: /^Feedback on try 1 from/ })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("region", { name: /^Feedback on try 1 from/ })).toBeVisible();

  // 320px: nothing scrolls sideways and the recap's actions fit and can be reached.
  await page.setViewportSize({ width: 320, height: 720 });
  await expect.poll(() => fits(page)).toBe(true);
  for (const control of [recap.getByRole("button", { name: "Revise this answer" }), recap.getByRole("link", { name: /^Next question: / })]) {
    await control.scrollIntoViewIfNeeded();
    await expect(control).toBeVisible();
    const b = await control.boundingBox();
    expect(b && b.height >= 32 && b.x >= 0 && b.x + b.width <= 320, "fits and is touch-sized").toBe(true);
  }
  await recap.getByRole("button", { name: "Revise this answer" }).click();
  await expect(page.getByText(/^Revising try 1: add “/)).toBeVisible();
  await expect.poll(() => fits(page)).toBe(true);

  // The dashboard counts the question once, however many tries.
  await page.setViewportSize({ width: 1440, height: 900 });
  page.on("dialog", (d) => void d.accept()); // leaving with an unsent revision asks first
  await page.goto("/dashboard");
  const summary = page.getByRole("region", { name: "Summary" });
  await expect(summary.getByText("Questions answered")).toBeVisible();
  await expect(summary).toContainText("1of 300, each counted once however many tries");
});
