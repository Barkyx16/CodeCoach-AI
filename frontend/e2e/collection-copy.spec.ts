import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Duplicate a collection (Volume 16, prompt 8) against the real API: a collection of three questions,
 * one marked done in its queue, duplicated through a lost reply ("Send again" makes one copy); the
 * copy has the three in order, nothing done and says whose copy it is; after a reload and from a
 * second browser it reads the same; the original's queue mark is still there. Axe in both themes.
 * Synthetic account.
 */
test("duplicate a collection through a lost reply: one copy, in order, a fresh queue", async ({ page, browser, request }) => {
  const email = `cp-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const qs = ((await (await request.get(`${API_URL}/api/v1/careers/registered-nurse/questions?page_size=3`, { headers: auth })).json()) as { items: { id: string; title: string }[] }).items;
  const coll = (await (await request.post(`${API_URL}/api/v1/me/collections`, { headers: auth, data: { name: "Week 1" } })).json()) as { id: string };
  for (const q of qs) {
    expect((await request.post(`${API_URL}/api/v1/me/collections/${coll.id}/items`, { headers: auth, data: { item_type: "question", track: "registered-nurse", ref_id: q.id } })).status()).toBe(200);
  }
  const first = ((await (await request.get(`${API_URL}/api/v1/me/collections/${coll.id}`, { headers: auth })).json()) as { item_list: { id: string }[] }).item_list[0]!;
  expect((await request.put(`${API_URL}/api/v1/me/collections/${coll.id}/items/${first.id}/done`, { headers: auth, data: { done: true } })).status()).toBe(200);

  const signIn = async (p: typeof page) => {
    await p.goto("/login");
    await p.getByLabel("Email").fill(email);
    await p.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
    await p.locator("#main").getByRole("button", { name: "Sign in" }).click();
    await expect(p).not.toHaveURL(/\/login$/);
  };
  await signIn(page);
  await page.goto(`/saved/collections/${coll.id}`);
  await page.getByRole("button", { name: "Duplicate" }).click();
  const form = page.getByRole("form", { name: "Duplicate “Week 1”" });
  await expect(form).toContainText("Its queue starts at the beginning, and this collection doesn't change.");
  // The first reply is lost after the server has made the copy.
  let lost = false;
  await page.route("**/duplicate", async (route) => {
    if (lost) return route.continue();
    lost = true;
    await route.fetch();
    await route.abort("connectionreset");
  });
  await form.getByRole("button", { name: "Make the copy" }).click();
  const alert = form.getByRole("alert");
  await expect(alert).toContainText("it makes one copy, not two");
  await alert.getByRole("button", { name: "Send again" }).click();

  await expect(page.getByRole("heading", { level: 1, name: "Week 1 (copy)" })).toBeVisible();
  await expect(page.getByText("A copy of “Week 1”.")).toBeVisible();
  const titles = qs.map((q) => q.title);
  const order = page.getByRole("list", { name: "Items in order" }).getByRole("listitem");
  await expect(order).toHaveCount(3);
  for (const [n, t] of titles.entries()) await expect(order.nth(n)).toContainText(t);
  await expect(page.getByText("Done in queue")).toHaveCount(0); // a fresh queue
  const all = (await (await request.get(`${API_URL}/api/v1/me/collections`, { headers: auth })).json()) as { name: string }[];
  expect(all.map((c) => c.name).sort()).toEqual(["Week 1", "Week 1 (copy)"]); // one copy

  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".collection-page").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }

  // After a reload, and from another browser, the copy reads the same.
  const url = page.url();
  await page.reload();
  for (const [n, t] of titles.entries()) await expect(order.nth(n)).toContainText(t);
  const other = await browser.newContext();
  const second = await other.newPage();
  await signIn(second);
  await second.goto(url);
  const there = second.getByRole("list", { name: "Items in order" }).getByRole("listitem");
  for (const [n, t] of titles.entries()) await expect(there.nth(n)).toContainText(t);
  // The original keeps its mark.
  await second.goto(`/saved/collections/${coll.id}`);
  await expect(second.getByText("Done in queue")).toHaveCount(1);
  await other.close();
});
