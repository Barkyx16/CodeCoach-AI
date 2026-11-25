import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Several saved items at once (Volume 11, prompt 5) against the real API: three bookmarks added to
 * a collection in one go while its reply is lost, sent again safely (each reported "already there",
 * nothing added twice); then two removed from the collection by keyboard, the bookmarks still there.
 * Axe in both themes. Synthetic account.
 */
test("add several to a collection through a lost reply, then remove two, bookmarks intact", async ({ page, request }) => {
  const email = `bk-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const qs = ((await (await request.get(`${API_URL}/api/v1/careers/registered-nurse/questions?page_size=3`, { headers: auth })).json()) as { items: { id: string; title: string }[] }).items;
  for (const q of qs) expect((await request.put(`${API_URL}/api/v1/me/bookmarks`, { headers: auth, data: { item_type: "question", track: "registered-nurse", ref_id: q.id } })).status()).toBe(200);
  const coll = (await (await request.post(`${API_URL}/api/v1/me/collections`, { headers: auth, data: { name: "Week 1" } })).json()) as { id: string };

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.goto("/saved");

  const bar = page.getByRole("group", { name: "Selected bookmarks" });
  await bar.getByRole("checkbox", { name: "Select all shown (3)" }).check();
  await expect(bar).toContainText("3 of 3 selected");
  await bar.getByLabel("Add the selected to").selectOption({ label: "Week 1 (0)" });
  // The first reply is lost after the server has saved it.
  let lost = false;
  await page.route("**/items/batch", async (route) => {
    if (lost) return route.continue();
    lost = true;
    await route.fetch();
    await route.abort("connectionreset");
  });
  await bar.getByRole("button", { name: "Add 3 to “Week 1”" }).click();
  const alert = page.getByRole("alert").filter({ hasText: "No reply came" });
  await expect(alert).toBeVisible();
  await alert.getByRole("button", { name: "Send again" }).click();
  const outcomes = page.getByRole("region", { name: /What happened: adding to “Week 1”/ });
  await expect(outcomes.getByRole("status")).toHaveText("3 already there. Nothing needs attention.");
  const after = (await (await request.get(`${API_URL}/api/v1/me/collections/${coll.id}`, { headers: auth })).json()) as { item_list: unknown[] };
  expect(after.item_list).toHaveLength(3); // once each

  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".saved-page").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }

  await page.goto(`/saved/collections/${coll.id}`);
  for (const q of qs.slice(0, 2)) {
    const box = page.getByRole("checkbox", { name: `Select: ${q.title}` });
    await box.focus();
    await page.keyboard.press("Space");
    await expect(box).toBeChecked();
  }
  const items = page.getByRole("group", { name: "Selected items" });
  await items.getByRole("button", { name: "Remove 2 from “Week 1”" }).click();
  const removed = page.getByRole("region", { name: /What happened: removing from “Week 1”/ });
  await expect(removed.getByRole("status")).toHaveText("2 removed. Nothing needs attention.");
  await expect(removed.getByRole("heading")).toBeFocused();
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".collection-page").analyze();
    expect(scan.violations.map((v) => v.id), `collection, ${theme}`).toEqual([]);
  }
  const marks = (await (await request.get(`${API_URL}/api/v1/me/bookmarks`, { headers: auth })).json()) as unknown[];
  expect(marks).toHaveLength(3); // removing from a collection touched no bookmark
});
