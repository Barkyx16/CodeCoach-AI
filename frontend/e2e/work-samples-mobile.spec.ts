import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/** Work samples on a phone (Volume 10, prompt 5): the brief and the editor stack, nothing scrolls
 * sideways, and a work sample can be written, previewed and sent by tapping. */
test("on a phone: the brief and editor stack, nothing scrolls sideways, and feedback arrives", async ({ page, request }) => {
  const email = `ws-m-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  expect((await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "project-manager" } })).status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).tap();
  await expect(page).not.toHaveURL(/\/login$/);

  await page.goto("/work-samples/ws-project-handoff");
  await expect(page.getByRole("region", { name: "The brief" })).toBeVisible();
  const noSideways = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  expect(await noSideways()).toBe(true);
  await page.getByLabel(/^Status/).fill("The move is on Saturday 14 June. Facilities signed off the floor plan.");
  await page.getByLabel(/^Budget/).fill("$18,400 spent of the $25,000 budget.");
  await page.getByRole("button", { name: "Preview" }).tap();
  await expect(page.getByRole("article", { name: "Preview" })).toContainText("$18,400 spent");
  expect(await noSideways()).toBe(true);
  await page.getByRole("button", { name: "Back to editing" }).tap();
  await page.getByRole("button", { name: "Get feedback" }).tap();
  await expect(page.getByRole("region", { name: "Missing" })).toContainText("Who to talk to");
  expect(await noSideways()).toBe(true);
});
