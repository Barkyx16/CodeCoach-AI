import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/** Comparing sample answers on a phone (Volume 10, prompt 6): one sample open at a time with the
 * other's marks counted, nothing scrolls sideways, an early reveal is confirmed and recorded, and
 * unsent marks come back after a reload. */
test("on a phone: one sample at a time, marks kept, an early reveal recorded", async ({ page, request }) => {
  const email = `cmp-m-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  expect((await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "customer-service-representative" } })).status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).tap();
  await expect(page).not.toHaveURL(/\/login$/);

  await page.goto("/compare/cmp-relevance");
  const noSideways = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  const a = page.getByRole("list", { name: "Answer A, sentence by sentence" });
  const b = page.getByRole("list", { name: "Answer B, sentence by sentence" });
  await expect(a).toBeVisible();
  await expect(b).toBeHidden();
  expect(await noSideways()).toBe(true);
  await a.getByRole("listitem").nth(1).getByRole("button", { name: "Strength" }).tap();
  await page.getByLabel("Why is it a strength?").fill("Gives a rule and the reason for it.");
  await page.getByRole("button", { name: /^Answer B/ }).tap();
  await expect(b).toBeVisible();
  await expect(a).toBeHidden();
  await expect(page.getByRole("button", { name: /^Answer A\s*· 1 marked$/ })).toHaveAttribute("aria-expanded", "false");
  expect(await noSideways()).toBe(true);

  await page.reload();
  await expect(page.getByText("Your unsent marks were restored from this device.")).toBeVisible();
  await expect(page.getByLabel("Why is it a strength?")).toHaveValue("Gives a rule and the reason for it.");

  await page.getByRole("button", { name: "Show the explanation now" }).tap();
  await page.getByRole("button", { name: "Show the explanation", exact: true }).tap();
  await expect(page.getByRole("region", { name: "The explanation", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Compare with the explanation" }).tap();
  await expect(page.getByRole("heading", { name: "Your reading and the explanation" })).toBeVisible();
  await expect(page.getByText("This reading was sent after the explanation was shown.", { exact: false })).toBeVisible();
  expect(await noSideways()).toBe(true);
});
