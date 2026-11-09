import { expect, test } from "./fixtures";

/**
 * The command palette on a phone (Volume 10, prompt 1): the "Go to" button is in the header next to
 * Menu, the dialog fits the screen without sideways scrolling, an option opens with a tap, and Close
 * puts focus back on the button. Signed out: only public pages are listed.
 */
test("on a phone: tap Go to, tap a page; Close returns to the button; nothing scrolls sideways", async ({ page }) => {
  await page.goto("/learn");
  const button = page.getByRole("button", { name: "Go to…" });
  await expect(button).toBeVisible(); // in the header, without opening the menu
  await button.tap();
  const dialog = page.getByRole("dialog", { name: "Go to a page" });
  await expect(dialog).toBeVisible();
  const box = (await dialog.boundingBox())!;
  const width = page.viewportSize()!.width;
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(width);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(dialog.getByRole("option")).toHaveText([/^Coding problems/, /^Interview questions/, /^Lessons/, /^Help/, /^Sign in/, /^Create account/]);

  await dialog.getByRole("button", { name: "Close" }).tap();
  await expect(dialog).toHaveCount(0);
  await expect(button).toBeFocused();

  await button.tap();
  await dialog.getByRole("option", { name: /^Help/ }).tap();
  await expect(page).toHaveURL(/\/help$/);
  await expect(dialog).toHaveCount(0);
});
