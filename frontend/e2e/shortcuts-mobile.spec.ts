import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/** Home shortcuts on a phone (Volume 11, prompt 2): the list wraps without sideways scrolling,
 * controls are full-size touch targets, and taps to move and remove stick through a reload.
 * Synthetic account. */
test("on a phone: shortcuts wrap, controls are big enough to tap, and changes stick", async ({ page, request }) => {
  const email = `sc-m-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  expect((await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "warehouse-associate" } })).status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).tap();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.goto("/dashboard");

  const card = page.getByRole("region", { name: "Your shortcuts" });
  await expect(card.getByRole("link")).toHaveCount(5);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  for (const box of await card.getByRole("link").evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height))) expect(box).toBeGreaterThanOrEqual(44);

  await card.getByRole("button", { name: "Edit shortcuts" }).tap();
  const down = card.getByRole("button", { name: "Move down: Interview questions" });
  expect((await down.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await down.tap();
  await expect(card.getByRole("status")).toHaveText("Interview questions moved to position 2 of 5.");
  await card.getByRole("button", { name: "Remove Stories" }).tap();
  await expect(card.getByRole("status")).toHaveText("Stories removed. 4 shortcuts left.");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await card.getByRole("button", { name: "Done" }).tap();

  await page.reload();
  await expect(card.getByRole("link")).toHaveCount(4);
  expect(await card.locator(".shortcut__label").allTextContents()).toEqual(["Notes", "Interview questions", "Applications", "My plan"]);
  await card.getByRole("link", { name: /Applications/ }).tap();
  await expect(page).toHaveURL(/\/applications$/);
});
