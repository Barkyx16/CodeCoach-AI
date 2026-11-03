import { expect, test, type Page } from "@playwright/test";

// The unified progress journey against the real backend: one coding and one non-coding career.

const filters = (page: Page) => page.getByRole("search", { name: "Filter history" });

async function historyFilters(page: Page) {
  return {
    career: await filters(page).getByRole("combobox", { name: /^Career/ }).inputValue(),
    type: await filters(page).getByLabel("Activity").inputValue(),
  };
}

test("coding: activity shows up honestly, and Back returns to the same filtered, scrolled list", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 640 });
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/\/problems\/two-sum$/);
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText(/Saved, but not run yet|All tests passed|didn't pass|Failed/i).first()).toBeVisible({ timeout: 60_000 });
  // Opening problems is recorded as activity (but never as an attempt).
  const slugs = ["valid-parentheses", "climbing-stairs", "coin-change", "binary-search", "maximum-subarray",
    "contains-duplicate", "reverse-string", "jump-game", "decode-ways", "product-except-self", "daily-temperatures"];
  // Slow the session restore on every full page load, as on a busy CI machine: each open must
  // still be recorded (the page waits for the session before fetching the problem).
  await page.route("**/api/v1/auth/refresh", async (route) => {
    await new Promise((r) => setTimeout(r, 1200));
    await route.continue();
  });
  for (const slug of slugs) {
    await page.goto(`/problems/${slug}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  }

  await page.goto("/dashboard");
  const resume = page.getByRole("region", { name: "Continue where you left off" });
  await expect(resume).toContainText("Two Sum");

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "History" }).click();
  await filters(page).getByRole("combobox", { name: /^Career/ }).selectOption("coding");
  await filters(page).getByLabel("Activity").selectOption("code_submission");
  await expect(page).toHaveURL(/career=coding/);
  await expect(page).toHaveURL(/type=code_submission/);
  await page.getByRole("link", { name: /Two Sum/ }).click();
  await expect(page).toHaveURL(/\/history\/submissions\//);
  await expect(page.getByRole("heading", { name: "Two Sum" })).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/career=coding&type=code_submission/);
  expect(await historyFilters(page)).toEqual({ career: "coding", type: "code_submission" });

  // Scroll position: open an item far down the list, come back with the browser's Back.
  await filters(page).getByLabel("Activity").selectOption("problem_opened");
  await expect(page.locator(".activity-list").getByRole("listitem")).toHaveCount(12);
  const last = page.getByRole("link", { name: /Two Sum/ });
  await last.scrollIntoViewIfNeeded();
  const before = await page.evaluate(() => window.scrollY);
  expect(before).toBeGreaterThan(100);
  await last.click();
  await expect(page).toHaveURL(/\/problems\/two-sum$/);
  await page.goBack();
  await expect(page).toHaveURL(/type=problem_opened/);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(before - 50);

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByRole("group", { name: "Analytics scope" }).getByLabel("Career")).toHaveValue("coding");
  await expect(page.getByRole("region", { name: "Practice statistics" })).toBeVisible();
});

test("non-coding: answer, find it in History, inspect Analytics, switch careers without losing history", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`progress-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("link", { name: "Practice questions" }).click();
  await page.getByRole("region", { name: "Question list" }).getByRole("link").first().click();
  const box = page.getByLabel("Your answer", { exact: true });
  await box.fill("When I assess a patient I start with airway, breathing and circulation, then vital signs and pain.");
  // An unsent answer survives a reload and is offered on the dashboard.
  await page.reload();
  await expect(box).toHaveValue(/airway, breathing and circulation/);
  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: "Continue where you left off" })).toContainText("unsent answer");
  await page.getByRole("link", { name: "Finish your answer" }).click();
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: "Feedback" })).toBeVisible();
  const questionUrl = page.url();

  // The dashboard updates from the real answer.
  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: "Summary" })).toContainText("1");
  await expect(page.getByText(/Acceptance/)).toHaveCount(0);

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "History" }).click();
  await filters(page).getByRole("combobox", { name: /^Career/ }).selectOption("registered-nurse");
  await filters(page).getByLabel("Activity").selectOption("written_answer");
  const row = page.locator(".activity-list").getByRole("listitem").first();
  await expect(row).toContainText(/Scored \d+\/100/);
  await row.getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`${new URL(questionUrl).pathname}\\?answer=`));
  await expect(page.getByRole("region", { name: /Feedback on your answer from/ })).toBeVisible();
  await page.getByRole("link", { name: "Back to History" }).click();
  await expect(page).toHaveURL(/career=registered-nurse&type=written_answer/);

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByRole("region", { name: /Registered Nurse summary/ })).toBeVisible();
  await expect(page.getByText(/Acceptance rate/)).toHaveCount(0);

  // Switch careers: history stays, and the old career is still inspectable.
  await page.goto("/settings");
  const careerForm = page.getByRole("form", { name: "Career" });
  await careerForm.getByLabel("Job you're preparing for").selectOption("barista");
  await careerForm.getByRole("button", { name: "Save career" }).click();
  await expect(careerForm.getByText(/Saved/)).toBeVisible();
  await page.goto("/history?career=registered-nurse");
  await expect(page.locator(".activity-list").getByRole("listitem").first()).toContainText(/Scored \d+\/100/);
  await page.goto("/analytics");
  const scope = page.getByRole("group", { name: "Analytics scope" }).getByLabel("Career");
  await expect(scope).toHaveValue("barista");
  await scope.selectOption("registered-nurse");
  await expect(page.getByText(/Your career setting is unchanged/)).toBeVisible();
  await expect(page.getByRole("region", { name: /Registered Nurse summary/ })).toContainText("1");
});
