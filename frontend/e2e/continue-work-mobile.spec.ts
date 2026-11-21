import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/** "Continue your work" on a phone (Volume 11, prompt 1): saved and device groups fit without
 * sideways scrolling, and the section can be hidden and shown. Synthetic account. */
test("on a phone: the section fits, and hiding it sticks until shown again", async ({ page, request }) => {
  const email = `cw-m-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "warehouse-associate" } });
  const { access_token: token, user } = (await reg.json()) as { access_token: string; user: { id: string } };
  await request.post(`${API_URL}/api/v1/me/notes`, { headers: { Authorization: `Bearer ${token}` }, data: { title: "Forklift checklist notes with a fairly long synthetic title", body: "x" } });
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).tap();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.evaluate((id) => localStorage.setItem(`codecoach.draft.v1.${id}.two-sum`, "class Solution {}"), user.id);
  await page.goto("/dashboard");
  const section = page.getByRole("region", { name: "Continue your work" });
  await expect(section.getByRole("group", { name: "Saved to your account" })).toContainText("Forklift checklist notes");
  await expect(section.getByRole("group", { name: "Only in this browser" })).toContainText("Open your draft");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await section.getByRole("button", { name: "Hide" }).tap();
  await page.reload();
  await expect(page.getByRole("button", { name: "Show it" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Continue your work" })).toHaveCount(0);
  await page.getByRole("button", { name: "Show it" }).tap();
  await expect(page.getByRole("region", { name: "Continue your work" })).toBeVisible();
});
