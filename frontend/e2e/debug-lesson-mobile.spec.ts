import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";

/** The lesson that prepares the debugging exercises (Volume 17, prompt 5), on a phone: it reads
 * without sideways scrolling, says it's a generated draft and names no reviewer (Volume 18, prompt 8:
 * it was labelled reviewed when nobody had reviewed it), offers an exercise to practise on, and axe
 * finds nothing in either theme. */
test("the failing-test lesson on a phone: readable, a draft said so, practice offered, accessible", async ({ page }) => {
  await page.goto("/learn/se-failing-test");
  await expect(page.getByRole("heading", { level: 1, name: "Fixing code from a failing test" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Fix “Coldest Reading”" })).toHaveAttribute("href", "/problems/debug-coldest-day");
  await expect(page.getByText("Generated draft: not reviewed yet")).toBeVisible();
  await expect(page.locator("#sources")).toContainText("Drafted in this repository with an AI coding assistant");
  await expect(page.locator("#sources")).not.toContainText("CodeCoach project author");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include("main").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }
});
