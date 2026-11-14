import { expect, test, type Page } from "./fixtures";

/**
 * Back returns to the right place (Volume 7, prompt 7), against the real API and router:
 * a filtered coding list, "View more", scrolled down, a problem opened from near the bottom;
 * then back by the page's own link and by the browser's Back and Forward. The list comes back
 * with the same filter, the same rows, near the same scroll position, and focus on the problem
 * the learner came back from. Opened directly, the problem offers the coding library instead.
 */
async function startAsGuest(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/\/welcome$/);
}

test("coding list → problem → back, by the page's link and the browser's buttons", async ({ page }) => {
  await startAsGuest(page);
  await page.goto("/problems?difficulty=medium");
  const list = page.locator(".problem-list");
  await expect(list.getByRole("link").first()).toBeVisible();
  await page.getByRole("button", { name: "View more" }).click();
  await expect(page).toHaveURL(/shown=15/);
  await expect(list.getByRole("link")).toHaveCount(15);
  const target = list.getByRole("link").nth(12);
  const href = await target.getAttribute("href");
  await target.scrollIntoViewIfNeeded();
  const scrolled = await page.evaluate(() => window.scrollY);
  expect(scrolled).toBeGreaterThan(200);
  await target.click();
  await expect(page).toHaveURL(new RegExp(`${href}$`));

  // The page's own way back: the same list, rows, scroll and the item focused.
  const crumbs = page.getByRole("navigation", { name: "Breadcrumb" });
  await crumbs.getByRole("link", { name: "Back to coding problems" }).click();
  await expect(page).toHaveURL(/difficulty=medium/);
  await expect(page).toHaveURL(/shown=15/);
  await expect(list.getByRole("link")).toHaveCount(15);
  await expect.poll(() => page.evaluate(() => document.activeElement?.getAttribute("href"))).toBe(href);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(scrolled - 150);

  // The browser's own Forward and Back do the same.
  await page.goForward();
  await expect(page).toHaveURL(new RegExp(`${href}$`));
  await page.goBack();
  await expect(page).toHaveURL(/shown=15/);
  await expect(list.getByRole("link")).toHaveCount(15);

  // Opened directly (a bookmark, a new tab): no "Back to …" that would lead nowhere, and the
  // coding library one click away.
  const direct = await page.context().newPage();
  await direct.goto(href!);
  const directCrumbs = direct.getByRole("navigation", { name: "Breadcrumb" });
  await expect(directCrumbs.getByRole("link", { name: /Coding problems/ })).toBeVisible();
  await expect(directCrumbs.getByRole("link", { name: "Back to coding problems" })).toHaveCount(0);
});
