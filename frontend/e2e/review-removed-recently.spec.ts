import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * A question removed from the review queue, put back after a reload (Volume 19, prompt 2), against
 * the real API: the page's own Undo is gone with the reload, so "Removed recently" lists it, with
 * when, and Put back returns it as it was. axe finds nothing on the section in either theme, and it
 * doesn't make the page scroll sideways. Synthetic account.
 */
test("remove, reload, put back from Removed recently", async ({ page, request }) => {
  const email = `rr-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const qs = ((await (await request.get(`${API_URL}/api/v1/careers/registered-nurse/questions?page_size=2`, { headers: auth })).json()) as { items: { id: string; title: string }[] }).items;
  for (const q of qs) {
    expect((await request.post(`${API_URL}/api/v1/me/reviews`, { headers: auth, data: { track: "registered-nurse", question_id: q.id } })).status()).toBeLessThan(300);
  }
  const before = (await (await request.get(`${API_URL}/api/v1/me/reviews`, { headers: auth })).json()) as { due: { title: string; due_at: string }[]; upcoming: { title: string; due_at: string }[] };
  const was = [...before.due, ...before.upcoming].find((i) => i.title === qs[0]!.title)!;

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.goto("/reviews");
  await page.getByRole("listitem", { name: qs[0]!.title }).getByRole("button", { name: "Remove" }).click();
  await expect(page.getByRole("button", { name: "Undo" })).toBeVisible();
  await page.reload(); // the page's Undo is gone with it
  await expect(page.getByRole("button", { name: "Undo" })).toHaveCount(0);

  const toggle = page.getByRole("button", { name: "Removed recently (1)" });
  await toggle.click();
  const row = page.getByRole("list", { name: "Removed recently" }).getByRole("listitem", { name: qs[0]!.title });
  await expect(row).toContainText(/Removed (just now|.* ago)/);
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".removed-recently").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await row.getByRole("button", { name: `Put back: ${qs[0]!.title}` }).click();
  await expect(page.getByText(`“${qs[0]!.title}” is back in your review queue, as it was.`)).toBeVisible();
  await expect(page.getByRole("button", { name: "Removed recently (0)" })).toBeFocused();
  const after = (await (await request.get(`${API_URL}/api/v1/me/reviews`, { headers: auth })).json()) as typeof before;
  const now = [...after.due, ...after.upcoming].find((i) => i.title === qs[0]!.title)!;
  expect(now.due_at).toBe(was.due_at); // as it was
});
