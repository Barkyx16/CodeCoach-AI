import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * What's new (Volume 11, prompt 10) against the real app: a nurse halfway through an answer sees
 * the header's dot without being interrupted, opens What's new from the keyboard, finds a change
 * they can use and one for coding careers they can't, opens a page from it, and comes back to the
 * answer they were writing, still there. The dot is gone afterwards. Axe in both themes.
 */
test("find an improvement and return to the answer in progress", async ({ page, request }) => {
  const email = `wn-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const q = ((await (await request.get(`${API_URL}/api/v1/careers/registered-nurse/questions?page_size=1`, { headers: auth })).json()) as { items: { id: string }[] }).items[0]!;

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);

  await page.goto(`/careers/registered-nurse/questions/${q.id}`);
  const answer = page.getByLabel("Your answer", { exact: true });
  await answer.fill("I checked her airway first, then called for help.");
  const link = page.getByRole("link", { name: /^What's new, \d+ new$/ });
  await expect(link).toBeVisible();
  await expect(answer).toBeFocused(); // the dot took nothing from the answer
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await link.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1, name: "What's new" })).toBeVisible();
  const lab = page.getByRole("listitem").filter({ has: page.getByRole("heading", { level: 3, name: "Debugging lab" }) });
  await expect(lab).toContainText("For careers with coding practice: not part of Registered Nurse practice.");
  await expect(lab.getByRole("link")).toHaveCount(0);
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".whats-new").analyze();
    expect(scan.violations.map((v) => v.id), `what's new, ${theme}`).toEqual([]);
  }

  await page.getByRole("link", { name: "Open Search your saved work" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Search your saved work" })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { level: 1, name: "What's new" })).toBeVisible();
  await page.goBack();
  await expect(answer).toHaveValue("I checked her airway first, then called for help.");
  await expect(page.getByRole("link", { name: "What's new", exact: true })).toBeVisible();
});
