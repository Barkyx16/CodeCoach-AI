import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/** "Your data" on a phone (Volume 10, prompt 10): an unsubmitted code draft is listed, and the
 * page fits without sideways scrolling. Synthetic account. */
test("on a phone: the device copy is listed and everything fits without sideways scrolling", async ({ page, request }) => {
  const email = `yd-m-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "warehouse-associate" } });
  const { user } = (await reg.json()) as { user: { id: string } };
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).tap();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.evaluate((id) => localStorage.setItem(`codecoach.draft.v1.${id}.two-sum`, "class Solution {\n  // unsubmitted\n}"), user.id);
  await page.goto("/settings/data");
  await expect(page.getByRole("region", { name: "On this device" })).toContainText("Code, not submitted");
  await expect(page.getByRole("region", { name: "Where your words go when they're processed" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
