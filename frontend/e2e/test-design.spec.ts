import AxeBuilder from "@axe-core/playwright";

import { expect, test, type APIRequestContext, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Test design (Volume 10, prompt 4) against the real API without a judge (the judged path is in
 * judge.spec.ts, E2E_JUDGE=1): reached from the coding library, cases written by keyboard with a
 * plain error for a malformed list, kept through a reload, then saved and honestly reported as not
 * run. Synthetic account.
 */
const PASSWORD = "CorrectHorse42";

async function signedIn(page: Page, request: APIRequestContext): Promise<void> {
  const email = `td-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const r = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD, career_track: "software-engineer" } });
  expect(r.status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

test("write cases by keyboard, keep them through a reload, and save them as not run without a judge", async ({ page, request }) => {
  await signedIn(page, request);
  await page.goto("/problems");
  await page.getByRole("link", { name: "Test design: write cases that find bugs" }).click();
  await page.getByRole("link", { name: "Test design: Count in Range" }).click();
  await expect(page.getByText("int countInRange(int[] nums, int lo, int hi)")).toBeVisible();
  await expect(page.getByRole("note")).toContainText("Code can't run on this server.");

  await page.getByLabel(/^nums/).focus();
  await page.keyboard.type("3, seven");
  await page.keyboard.press("Tab");
  await page.keyboard.type("1");
  await page.keyboard.press("Tab");
  await page.keyboard.type("7");
  await page.keyboard.press("Tab");
  await page.keyboard.type("2");
  await page.getByRole("button", { name: "Save my cases (not run)" }).click();
  await expect(page.getByText("Whole numbers separated by commas, like 3, -1, 7.")).toBeVisible();
  await page.getByLabel(/^nums/).fill("3, 7");

  await page.reload();
  await expect(page.getByText("Your unsent cases were restored from this device.")).toBeVisible();
  await expect(page.getByLabel(/^nums/)).toHaveValue("3, 7");
  const scan = await new AxeBuilder({ page }).include(".td-layout").analyze();
  expect(scan.violations.map((v) => v.id)).toEqual([]);

  await page.getByRole("button", { name: "Save my cases (not run)" }).click();
  await expect(page.getByRole("heading", { name: "Report" })).toBeFocused();
  await expect(page.getByText(/these cases weren't run/).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "What your cases show" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Your earlier runs" })).toContainText("not run");
});
