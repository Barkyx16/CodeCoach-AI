import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/** Code-review practice on a phone (Volume 10, prompt 3): the code scrolls inside its own box, the
 * page never scrolls sideways, and a finding can be written and sent by tapping. */
test("on a phone: the code fits, nothing scrolls sideways, and a review can be sent", async ({ page, request }) => {
  const email = `review-m-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  expect((await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "software-engineer" } })).status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).tap();
  await expect(page).not.toHaveURL(/\/login$/);

  await page.goto("/code-reviews/review-second-largest");
  const code = page.getByLabel(/^The code under review/);
  await expect(code).toContainText("int second = -1;");
  const width = page.viewportSize()!.width;
  const box = (await code.boundingBox())!;
  expect(box.x + box.width).toBeLessThanOrEqual(width);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await page.getByRole("button", { name: "Add a finding" }).tap();
  await page.getByLabel("From line").fill("9");
  await page.getByLabel("To line").fill("10");
  await page.getByLabel("What's wrong").fill("A repeat of the largest value is stored as the second largest.");
  await page.getByRole("button", { name: "Send review and compare" }).tap();
  await expect(page.getByRole("region", { name: "Your findings" }).getByText("Points at an authored defect")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
