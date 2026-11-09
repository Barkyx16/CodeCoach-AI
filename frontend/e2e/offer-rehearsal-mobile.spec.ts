import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/** Offer rehearsals on a phone (Volume 10, prompt 8): the card and conversation stack without
 * sideways scrolling, an unsent turn survives a reload, the conversation resumes where it was, and
 * stopping early still gives a debrief. */
test("on a phone: fits, keeps an unsent turn through a reload, resumes, and stops with a debrief", async ({ page, request }) => {
  const email = `offer-m-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  expect((await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "warehouse-associate" } })).status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).tap();
  await expect(page).not.toHaveURL(/\/login$/);

  await page.goto("/offers/offer-warehouse-team-lead");
  await page.getByRole("button", { name: "Start the rehearsal" }).tap();
  const noSideways = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  await expect(page.getByLabel("What you'd say")).toBeVisible();
  expect(await noSideways()).toBe(true);
  await page.getByLabel("What you'd say").fill("Is parking included?");
  await page.getByRole("button", { name: "Say it" }).tap();
  await expect(page.getByRole("list", { name: "Transcript" })).toContainText("Parking: That isn't set out in the offer you have.");
  await page.getByLabel("What you'd say").fill("And what's the hourly rate?");
  await page.reload();
  await expect(page.getByLabel("What you'd say")).toHaveValue("And what's the hourly rate?");
  await expect(page.getByRole("list", { name: "Transcript" })).toContainText("Parking: That isn't set out in the offer you have.");
  await page.getByRole("button", { name: "Stop and see the debrief" }).tap();
  await expect(page.getByRole("region", { name: "Debrief" })).toContainText("You didn't reach the counteroffer.");
  expect(await noSideways()).toBe(true);
});
