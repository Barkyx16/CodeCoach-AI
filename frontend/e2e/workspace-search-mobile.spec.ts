import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/** Search your saved work on a phone (Volume 11, prompt 3): the form and results fit without
 * sideways scrolling, and a long result wraps. Synthetic account. */
test("on a phone: search and results fit", async ({ page, request }) => {
  const email = `ws-m-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "warehouse-associate" } });
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  await request.post(`${API_URL}/api/v1/me/notes`, { headers: auth, data: { title: "Forklift pre-shift checklist with a deliberately long synthetic title", body: "Check the forklift horn, brakes and forks before every shift; log anything odd." } });
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).tap();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.goto("/search");
  await page.getByLabel("Words to find").fill("forklift");
  await expect(page.getByRole("region", { name: "Results" }).getByRole("link")).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole("checkbox", { name: "Include archived" }).tap();
  await expect(page.getByRole("checkbox", { name: "Include archived" })).toBeChecked();
});
