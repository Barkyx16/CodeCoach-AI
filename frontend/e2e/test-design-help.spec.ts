import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";

/**
 * The help before a test-design run (Volume 19, prompt 3), against the real API (no judge here, so
 * cases are saved as not run): a run saved before the faulty versions were shown has none; after
 * they're shown, the next run's report says "Solution revealed", and both rows in "Your earlier
 * runs" say what came before each. axe finds nothing on the report in either theme.
 */
test("a run after the faulty versions were shown says so; one before doesn't", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page.getByRole("button", { name: "Start this problem" })).toBeVisible();
  await page.goto("/test-design/tests-count-in-range");
  await page.getByLabel(/^nums/).nth(0).fill("3, 7");
  await page.getByLabel(/^lo/).nth(0).fill("1");
  await page.getByLabel(/^hi/).nth(0).fill("7");
  await page.getByLabel("Expected output").nth(0).fill("2");
  const save = page.getByRole("button", { name: /Save my cases \(not run\)|Run my cases/ });
  await save.click();
  await expect(page.getByText("In-app help before this run:")).toBeVisible();
  await expect(page.locator(".attempt-conditions").first()).toContainText("No in-app help recorded");

  await page.getByRole("button", { name: "Stuck? Show what the faulty versions get wrong" }).click();
  await page.getByRole("button", { name: "Show the faulty versions" }).click();
  await expect(page.getByRole("region", { name: "The faulty versions" })).toBeVisible();
  await save.click();
  const help = page.locator(".attempt-conditions").first();
  await expect(help).toContainText("Solution revealed");
  await expect(help).toContainText("The faulty versions were shown before these cases were written");
  const earlier = page.getByRole("region", { name: "Your earlier runs" }).getByRole("listitem");
  await expect(earlier).toHaveCount(2);
  await expect(earlier.nth(0)).toContainText("In-app help: Solution revealed");
  await expect(earlier.nth(1)).toContainText("In-app help: No in-app help recorded");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".attempt-conditions").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }
});
