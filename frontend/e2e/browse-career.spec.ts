import { chooseJob, expect, test, type Page } from "./fixtures";

/**
 * Viewing a career without changing the account (Volume 9, prompt 4), against the real API: a
 * synthetic nursing account opens coding and another career's links, follows breadcrumbs and
 * Back, an unknown value and a bookmark; its own career is unchanged throughout; a deliberate
 * change in Settings is what changes it. Signed out, a copied link opens that career.
 */
async function newNurse(page: Page): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`browse-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
}
const line = (page: Page) => page.locator(".browse-note");

test("a nurse browses coding and another career, follows breadcrumbs and Back; their career changes only in Settings", async ({ page }) => {
  await newNurse(page);

  // Coding, from an explicit link.
  await page.goto("/problems?career=software-engineer");
  const list = page.locator(".problem-list");
  await expect(list.getByRole("link").first()).toBeVisible();
  await expect(line(page)).toContainText("Viewing Software Engineer coding problems. Your plan and progress follow your own career, Registered Nurse.");
  await expect(page.getByRole("link", { name: /Try a mock interview/ })).toHaveAttribute("href", "/interviews?career=software-engineer");
  const problem = list.getByRole("link").first();
  const href = await problem.getAttribute("href");
  await problem.click();
  await expect(page).toHaveURL(new RegExp(`${href}$`));
  await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Back to coding problems" }).click();
  await expect(page).toHaveURL(/\/problems\?career=software-engineer/);
  // The breadcrumb went back in this tab's history: Forward returns to the problem, Back to the list.
  await page.goForward();
  await expect(page).toHaveURL(new RegExp(`${href}$`));
  await page.goBack();
  await expect(page).toHaveURL(/\/problems\?career=software-engineer/);
  await expect(line(page)).toBeVisible();

  // Another career's questions, and its breadcrumb.
  await page.goto("/problems?career=barista");
  await expect(page.getByRole("heading", { name: "Barista interview questions" })).toBeVisible();
  await expect(line(page)).toContainText("Viewing Barista interview questions.");
  await page.locator(".problem-list").getByRole("link").first().click();
  await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Barista questions" }).click();
  await expect(page.getByRole("heading", { name: "Barista interview questions" })).toBeVisible();

  // An unknown value, and the way back to their own.
  await page.goto("/problems?career=not-a-job");
  await expect(page.getByRole("heading", { name: "Registered Nurse interview questions" })).toBeVisible();
  await expect(line(page)).toContainText("There's no career called “not-a-job” here");

  // A bookmark opened in a new tab of the same browser.
  const bookmark = await page.context().newPage();
  await bookmark.goto("/learn?career=software-engineer");
  await expect(bookmark.getByRole("heading", { name: "Software Engineer lessons" })).toBeVisible();
  await expect(line(bookmark)).toContainText("Your plan and progress follow your own career, Registered Nurse.");
  await bookmark.close();

  // Nothing above changed their career: their library and goals are still nursing.
  await page.goto("/problems");
  await expect(page.getByRole("heading", { name: "Registered Nurse interview questions" })).toBeVisible();
  await expect(line(page)).toHaveCount(0);
  await page.goto("/plan/goals");
  await expect(page.getByText("YOUR PLAN · REGISTERED NURSE")).toBeVisible();

  // A deliberate change, in Settings.
  await page.goto("/settings#account");
  const row = page.getByRole("form", { name: "Career" });
  await chooseJob(row, "barista");
  await row.getByRole("button", { name: "Save career" }).click();
  await expect(row.getByText("Saved. Your practice questions now match this job.")).toBeVisible();
  await page.goto("/problems");
  await expect(page.getByRole("heading", { name: "Barista interview questions" })).toBeVisible();
  await expect(line(page)).toHaveCount(0);
});

test("signed out, a copied link opens that career; an unknown one says what's shown instead", async ({ page }) => {
  await page.goto("/problems?career=registered-nurse");
  await expect(page.getByRole("heading", { name: "Registered Nurse interview questions" })).toBeVisible();
  await expect(line(page)).toHaveCount(0);
  await page.goto("/problems?career=nope&view=questions");
  await expect(page.getByRole("heading", { name: "Software Engineer interview questions" })).toBeVisible();
  await expect(line(page)).toContainText("There's no career called “nope” here, so these are Software Engineer interview questions.");
});
