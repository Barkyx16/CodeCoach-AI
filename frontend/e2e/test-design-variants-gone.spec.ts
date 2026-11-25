import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * The faulty versions are shown only where the showing is recorded (Volume 20, prompt 4), against the
 * real API. Signed out, the public route answers 410 with the reason, and the exercise's page asks to
 * sign in first, then brings you back to it; there, "Show the faulty versions" records the showing
 * before it shows them. Synthetic account.
 */
const SLUG = "tests-count-in-range";

test("signed out the faulty versions aren't served; signed in, showing them is recorded", async ({ page, request }) => {
  const gone = await request.get(`${API_URL}/api/v1/test-design/${SLUG}/variants`);
  expect(gone.status()).toBe(410);
  const body = (await gone.json()) as { error: { code: string; message: string } };
  expect(body.error.code).toBe("faulty_versions_need_sign_in");
  expect(body.error.message).toContain("Sign in");
  // The public summary still says how many there are.
  const summary = (await (await request.get(`${API_URL}/api/v1/test-design/${SLUG}`)).json()) as { variant_count: number };
  expect(summary.variant_count).toBeGreaterThan(0);

  const email = `td-gone-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "software-engineer" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };

  // Signed out, the page asks to sign in and comes back to the exercise.
  await page.goto(`/test-design/${SLUG}`);
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(new RegExp(`/test-design/${SLUG}$`));

  await page.getByRole("button", { name: "Stuck? Show what the faulty versions get wrong" }).click();
  const showing = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith(`/me/test-design/${SLUG}/variants`));
  await page.getByRole("button", { name: "Show the faulty versions" }).click();
  expect((await showing).status()).toBe(200);
  await expect(page.locator("section", { has: page.locator("#td-variants") })).toContainText("Version A");
  // Signed in, the public route still answers 410: only the recorded showing serves them.
  expect((await request.get(`${API_URL}/api/v1/test-design/${SLUG}/variants`, { headers: auth })).status()).toBe(410);
});
