import { chooseJob, expect, test } from "./fixtures";

const STRONG =
  "Last winter, while I was working nights, a patient's oxygen dropped during my 2 a.m. assessment. I was " +
  "responsible for five patients, so I moved fast. I checked his vital signs again and started oxygen per protocol. " +
  "I called the rapid response team and asked the charge nurse to cover my other patients. I updated the doctor " +
  "and documented everything. As a result, he was stable within 30 minutes, and I learned to escalate early.";

test("a new nurse skips setup, takes the baseline, and the plan adapts for stated reasons", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`plan-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click(); // the optional welcome

  const today = page.getByRole("region", { name: "Today" });
  await today.getByRole("button", { name: "Not now, use a starter plan" }).click();
  await expect(today.getByRole("button", { name: "Not now, use a starter plan" })).toHaveCount(0);
  const baseline = today.getByRole("article", { name: "Baseline check: 3 short questions" });
  await expect(baseline).toContainText("isn't enough evidence");
  await baseline.getByRole("button", { name: /Start/ }).click();

  await expect(page.getByText(/QUESTION 1 OF 3/)).toBeVisible();
  await page.getByLabel("Your answer", { exact: true }).fill(STRONG);
  await page.getByRole("button", { name: "Next question" }).click();
  await expect(page.getByText(/QUESTION 2 OF 3/)).toBeVisible();
  await page.getByLabel("Your answer", { exact: true }).fill("I would just do my best and ask for help if needed.");
  await page.getByRole("button", { name: "Next question" }).click();
  await expect(page.getByText(/QUESTION 3 OF 3/)).toBeVisible();
  await page.getByRole("button", { name: "Skip" }).click();
  await expect(page.getByRole("heading", { name: /interview results/ })).toBeVisible();

  await page.goto("/dashboard");
  await expect(today.getByText("Your plan changed")).toBeVisible();
  await expect(today.getByText(/Done: “Baseline check: 3 short questions” \(round finished\)/)).toBeVisible();
  await expect(today.getByText(/Added “Retry:/).first()).toBeVisible(); // one per weak answer (up to two)

  // Refreshing keeps the same plan and progress.
  await page.goto("/plan");
  const version = await page.getByText(/^Version \d+\./).textContent();
  await page.reload();
  await expect(page.getByText(/^Version \d+\./)).toHaveText(version!);
  await expect(page.getByRole("heading", { name: "How your answers scored" })).toBeVisible();

  // Skipping sets an activity aside; it never shows as done.
  const first = page.getByRole("region", { name: /Up next/ }).getByRole("article").first();
  const title = await first.getByRole("heading").textContent();
  await first.getByRole("button", { name: "More options" }).click();
  await first.getByRole("button", { name: "Skip for now" }).click();
  const aside = page.getByRole("region", { name: /Set aside/ });
  await expect(aside.getByRole("article", { name: title! })).toContainText("Skipped");
  await expect(page.getByRole("region", { name: /Done in this version/ }).getByRole("article", { name: title! })).toHaveCount(0);

  // Open an activity page and come back with the browser's Back.
  const next = page.getByRole("region", { name: /Up next/ }).getByRole("link", { name: /Start/ }).first();
  await next.click();
  await expect(page).not.toHaveURL(/\/plan$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/plan$/);
  await expect(page.getByRole("heading", { name: "Your plan" })).toBeVisible();
});

test("a software engineer's plan differs and includes coding", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await page.getByRole("button", { name: "Start this problem" }).click(); // the optional welcome
  await expect(page).toHaveURL(/two-sum/);
  await page.goto("/plan");
  await expect(page.getByText("YOUR PRACTICE PLAN · SOFTWARE ENGINEER")).toBeVisible();
  await expect(page.getByRole("article").filter({ hasText: "Coding problem" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Code the judge ran" })).toBeVisible();
});
