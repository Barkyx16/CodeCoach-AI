import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/** Offer comparisons on a phone (Volume 10, prompt 9): offers stack without sideways scrolling,
 * amounts can be hidden on screen, and Copy as text previews exactly what it would copy. */
test("on a phone: stacked, no sideways scroll, amounts hidden on request, an exact copy preview", async ({ page, request }) => {
  const email = `oc-m-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  expect((await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "warehouse-associate" } })).status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).tap();
  await expect(page).not.toHaveURL(/\/login$/);

  await page.goto("/offers/compare");
  await page.getByRole("button", { name: "Start with a fictional example" }).tap();
  await expect(page.getByRole("region", { name: "How the numbers are worked out" })).toBeVisible();
  const noSideways = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  expect(await noSideways()).toBe(true);
  const [first, second] = await page.locator(".oc-offer").all();
  const a = await first!.boundingBox();
  const b = await second!.boundingBox();
  expect(b!.y).toBeGreaterThan(a!.y + a!.height - 1); // stacked, not side by side
  await page.getByRole("checkbox", { name: "Hide amounts on screen" }).tap();
  await expect(page.locator(".oc-page")).toHaveClass(/is-hidden/);
  await page.getByRole("button", { name: "Copy as text…" }).tap();
  const dialog = page.getByRole("dialog", { name: "Copy as text: exactly this" });
  await expect(dialog).toContainText("Fictional example: two offers with gaps");
  await expect(dialog).toContainText("Nothing is sent, shared or published.");
  expect(await noSideways()).toBe(true);
});
