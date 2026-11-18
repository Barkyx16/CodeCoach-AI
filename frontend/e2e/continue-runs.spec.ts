import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Continue your work takes a learner back to an unfinished scenario run and a test-design run
 * (Volume 19, prompt 6), against the real API: a scenario run left after a decision is listed as a
 * started "Scenario run" with Resume, which opens it at the step it was left on; a test-design run
 * saved here (no judge, so not run) is a "Test design run" in its run list's words, opening its report.
 * Loading the dashboard starts and resumes nothing. Synthetic account.
 */
test("Resume opens a scenario run at its current step, and a test-design run opens its report", async ({ page, request }) => {
  const email = `cont-runs-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  expect((await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } })).status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);

  // A scenario run, left after its first decision.
  await page.goto("/scenarios/rn-two-patients");
  await page.getByRole("button", { name: "Start the scenario" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel(/Bed 7, because their medicine is due/).check();
  await page.getByRole("button", { name: "Confirm this decision" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Meanwhile" })).toBeVisible();

  // A test-design run, saved here without a judge.
  await page.goto("/test-design/tests-count-in-range");
  await page.getByLabel(/^nums/).nth(0).fill("3, 7");
  await page.getByLabel(/^lo/).nth(0).fill("1");
  await page.getByLabel(/^hi/).nth(0).fill("7");
  await page.getByLabel("Expected output").nth(0).fill("2");
  await page.getByRole("button", { name: /Save my cases \(not run\)|Run my cases/ }).click();
  await expect(page.locator("#td-result")).toBeVisible();

  const posts: string[] = [];
  page.on("request", (r) => { if (r.method() !== "GET" && !r.url().endsWith("/auth/refresh")) posts.push(`${r.method()} ${r.url()}`); });
  await page.goto("/dashboard");
  const saved = page.getByRole("region", { name: "Continue your work" }).getByRole("group", { name: "Saved to your account" });
  const run = saved.getByRole("link", { name: /Test design: Count in Range/ });
  await expect(run).toContainText(/Test design run · (Not run: this server can't run code|Waiting for the judge|Told apart \d of 4 faulty versions) · version 1 · (saved|finished) .* · Open/);
  const scenario = saved.getByRole("link", { name: /Two call lights at once/ });
  await expect(scenario).toContainText(/Scenario run · last step .* · Resume/); // left after a decision (Volume 20, prompt 6)
  expect(posts).toEqual([]); // loading the section starts and resumes nothing

  await scenario.click();
  await expect(page).toHaveURL(/\/scenarios\/attempts\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { level: 2, name: "Meanwhile" })).toBeVisible();
  await expect(page.getByRole("list", { name: "What has happened so far" })).toContainText("Risky");

  await page.goto("/dashboard");
  await run.click();
  await expect(page).toHaveURL(/\/test-design\/tests-count-in-range\?attempt=/);
  await expect(page.locator("#td-result")).toBeVisible();
});
