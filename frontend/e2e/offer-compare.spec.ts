import AxeBuilder from "@axe-core/playwright";

import { expect, test, type APIRequestContext, type Page, setTheme } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Offer comparisons (Volume 10, prompt 9) against the real API: the fictional example with its
 * gaps, an hourly offer put on a yearly basis once its weeks are entered, a dated rate converting
 * one currency, weights ordering the offers with every point shown, a save that survives a reload,
 * and no accessibility violations in either theme. Synthetic account.
 */
const PASSWORD = "CorrectHorse42";

async function signedIn(page: Page, request: APIRequestContext): Promise<void> {
  const email = `oc-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const r = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD, career_track: "logistics-coordinator" } });
  expect(r.status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

test("the fictional example, a yearly basis, a dated rate, weights explained, and a save that survives a reload", async ({ page, request }) => {
  await signedIn(page, request);
  await page.goto("/offers/compare");
  await page.getByRole("button", { name: "Start with a fictional example" }).click();
  const figures = page.getByRole("region", { name: "How the numbers are worked out" });
  await expect(figures).toContainText("Unknown: Enter the weeks paid a year to put hourly pay on a yearly basis.");
  await expect(figures).toContainText("These offers are in GBP, USD.");

  await page.getByLabel("Weeks paid a year").first().fill("52");
  await expect(figures).toContainText("21.50 USD an hour × 40 hours a week × 52 weeks = 44,720 USD a year");
  await page.getByRole("button", { name: "Add a rate" }).click();
  await page.getByLabel("Rate", { exact: true }).fill("0.8");
  await page.getByLabel("As of", { exact: true }).fill("2026-11-01");
  await page.getByLabel("Also show figures in").selectOption("GBP");
  await expect(figures).toContainText("44,720 USD × 0.8 = 35,776 GBP");
  await expect(figures).toContainText("1 USD = 0.8 GBP (your rate for 2026-11-01)");
  await page.getByRole("checkbox", { name: "Use my weights to order the offers (you can turn this off)" }).check();
  const weighted = page.getByRole("region", { name: "Your weighted ordering" });
  await expect(weighted).toContainText("not a recommendation or an objectively best offer");
  await expect(weighted).toContainText("Commute: not counted (unknown)");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".oc-page").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Saved as version 2. Only you can see it.")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("region", { name: "How the numbers are worked out" })).toContainText("44,720 USD × 0.8 = 35,776 GBP");
  await expect(page.getByRole("region", { name: "Unsaved changes" })).toHaveCount(0);
});
