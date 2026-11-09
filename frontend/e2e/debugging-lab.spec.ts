import AxeBuilder from "@axe-core/playwright";

import { expect, test, type APIRequestContext, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * The debugging lab (Volume 10, prompt 2) against the real API, without a judge (the judged path is
 * in judge.spec.ts, E2E_JUDGE=1): reached from the coding library, the brief names the failing case,
 * the explanation waits until asked, an attempt is saved and honestly not called fixed, and History
 * shows the code it started from. Synthetic account.
 */
const PASSWORD = "CorrectHorse42";

async function signedIn(page: Page, request: APIRequestContext): Promise<void> {
  const email = `lab-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const r = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD, career_track: "software-engineer" } });
  expect(r.status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

test("from the library to a saved attempt, without a judge: the brief, the reveal, an honest debrief and History", async ({ page, request }) => {
  await signedIn(page, request);
  await page.goto("/problems");
  await page.getByRole("link", { name: "Debugging lab: fix programs with a known bug" }).click();
  await expect(page.getByRole("heading", { name: "Fix a broken program", level: 1 })).toBeVisible();
  await page.getByRole("link", { name: "Fix: Count Within a Limit" }).click();

  const brief = page.getByRole("region", { name: "Fix the bug" });
  await expect(brief).toContainText("nums = [4, 8, 3], limit = 5 should give 2");
  await expect(page.locator(".monaco-editor .view-lines").first()).toContainText("nums.length - 1");
  await expect(brief).not.toContainText("stops before the last index");
  const scan = await new AxeBuilder({ page }).include(".debug-brief").analyze();
  expect(scan.violations.map((v) => v.id)).toEqual([]);

  await brief.getByRole("button", { name: "Stuck? Show the explanation" }).click();
  await brief.getByRole("button", { name: "Show the explanation" }).click();
  await expect(brief).toContainText("it stops before the last index");
  await expect(brief.getByText("Yours doesn't have to look like this: the tests decide.")).toBeVisible();

  // No judge on this server: the attempt is saved, and nobody says it's fixed.
  await page.getByRole("button", { name: /^Save attempt/ }).click();
  const debrief = page.getByRole("region", { name: "Debugging debrief" });
  await expect(debrief.getByRole("heading", { name: "Saved, not checked" })).toBeVisible();
  await expect(debrief).not.toContainText("Fixed");

  await page.goto("/history");
  await page.getByRole("link", { name: /Fix: Count Within a Limit/ }).first().click();
  await expect(page.getByRole("heading", { name: "Started from" })).toBeVisible();
  await expect(page.getByLabel("Starting code")).toContainText("nums.length - 1");
});
