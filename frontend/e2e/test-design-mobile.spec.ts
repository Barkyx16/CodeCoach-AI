import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/** Test design on a phone (Volume 10, prompt 4): the case fields fit, nothing scrolls sideways,
 * and a case can be written and saved by tapping. */
test("on a phone: the case fields fit, nothing scrolls sideways, and cases can be saved", async ({ page, request }) => {
  const email = `td-m-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  expect((await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "software-engineer" } })).status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).tap();
  await expect(page).not.toHaveURL(/\/login$/);

  await page.goto("/test-design/tests-longest-run");
  const nums = page.getByLabel(/^nums/);
  await expect(nums).toBeVisible();
  const width = page.viewportSize()!.width;
  const box = (await nums.boundingBox())!;
  expect(box.x + box.width).toBeLessThanOrEqual(width);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await nums.fill("1, 2, 2, 2");
  await page.getByLabel("Expected output").fill("3");
  await page.getByRole("button", { name: "Save my cases (not run)" }).tap();
  await expect(page.getByText(/these cases weren't run/).first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
