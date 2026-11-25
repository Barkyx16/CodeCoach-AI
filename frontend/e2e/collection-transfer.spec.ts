import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Move chosen items to another collection (Volume 17, prompt 6) against the real API: two of three
 * questions, one marked done in its queue, moved through a lost reply ("Send again" carries the first
 * request's key, so the server gives back what it did, "2 moved", and nothing is done twice: Volume 18,
 * prompt 5); the form said what the other collection has, what leaves and what
 * the queue will skip; axe finds nothing on the form in both themes. After a reload, both collections
 * read as the server holds them: the two at the end of the other one in this one's order, at the
 * versions they were added at, the queue mark left behind. Synthetic account.
 */
test("move two items through a lost reply: each arrives once, as it was, and both collections say so after a reload", async ({ page, request }) => {
  const email = `mv-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const qs = ((await (await request.get(`${API_URL}/api/v1/careers/registered-nurse/questions?page_size=4`, { headers: auth })).json()) as { items: { id: string; title: string }[] }).items;
  const make = async (name: string, ids: string[]) => {
    const c = (await (await request.post(`${API_URL}/api/v1/me/collections`, { headers: auth, data: { name } })).json()) as { id: string };
    for (const id of ids) {
      expect((await request.post(`${API_URL}/api/v1/me/collections/${c.id}/items`, { headers: auth, data: { item_type: "question", track: "registered-nurse", ref_id: id } })).status()).toBe(200);
    }
    return c.id;
  };
  type Item = { id: string; ref_id: string; content_version: number | null; queue_done: boolean };
  const read = async (id: string) =>
    (await (await request.get(`${API_URL}/api/v1/me/collections/${id}`, { headers: auth })).json()) as { item_list: Item[]; queue_position: number };
  const week1 = await make("Week 1", [qs[0]!.id, qs[1]!.id, qs[2]!.id]);
  const week2 = await make("Week 2", [qs[3]!.id]);
  const before = (await read(week1)).item_list;
  expect((await request.put(`${API_URL}/api/v1/me/collections/${week1}/items/${before[0]!.id}/done`, { headers: auth, data: { done: true } })).status()).toBe(200);
  expect((await request.put(`${API_URL}/api/v1/me/collections/${week1}/queue`, { headers: auth, data: { position: 1 } })).status()).toBe(200);

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.goto(`/saved/collections/${week1}`);
  for (const q of [qs[0]!, qs[2]!]) await page.getByRole("checkbox", { name: `Select: ${q.title}` }).check();
  await page.getByRole("button", { name: "Move 2 to…" }).click();
  const form = page.getByRole("form", { name: "Move 2 items to another collection" });
  await form.getByLabel("To collection").selectOption({ label: "Week 2 (1 item)" });
  const words = form.getByRole("list", { name: "Before you move them" });
  await expect(words).toContainText("“Week 2” has none of these 2 yet.");
  await expect(words).toContainText(`Leaves “Week 1”, each once it's in “Week 2”: “${qs[0]!.title}” and “${qs[2]!.title}”.`);
  await expect(words).toContainText(`Its queue (at item 2 of 3) will skip 1 not reached yet: “${qs[2]!.title}”.`);
  await expect(words).toContainText(`“${qs[0]!.title}” was marked done in this queue; that mark isn't carried to “Week 2”.`);
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".collection-page form").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }

  // The first reply is lost after the server has moved them.
  let lost = false;
  await page.route("**/items/transfer", async (route) => {
    if (lost) return route.continue();
    lost = true;
    await route.fetch();
    await route.abort("connectionreset");
  });
  await form.getByRole("button", { name: "Move 2 to “Week 2”" }).click();
  const alert = page.getByRole("alert").filter({ hasText: "No reply came" });
  await expect(alert).toContainText("Sending the same ones again is safe");
  await alert.getByRole("button", { name: "Send again" }).click();
  const outcomes = page.getByRole("region", { name: "What happened: moving to “Week 2”" });
  await expect(outcomes.getByRole("status")).toHaveText("2 moved. Nothing needs attention.");
  await expect(page.getByText(/This was sent again after no reply came/)).toContainText(
    "these are what the first request did, and nothing was done twice.");
  await expect(page.getByRole("link", { name: "“Week 2”" })).toHaveAttribute("href", `/saved/collections/${week2}`);

  // After a reload: what's left here, and the other collection with the two at its end, in this order.
  await page.reload();
  const here = page.getByRole("list", { name: "Items in order" }).getByRole("listitem");
  await expect(here).toHaveCount(1);
  await expect(here.first()).toContainText(qs[1]!.title);
  await page.goto(`/saved/collections/${week2}`);
  const there = page.getByRole("list", { name: "Items in order" }).getByRole("listitem");
  await expect(there).toHaveCount(3);
  for (const [n, q] of [qs[3]!, qs[0]!, qs[2]!].entries()) await expect(there.nth(n)).toContainText(q.title);
  await expect(page.getByText("Done in queue")).toHaveCount(0); // the mark stayed behind
  const arrived = (await read(week2)).item_list;
  expect(arrived.map((i) => i.ref_id)).toEqual([qs[3]!.id, qs[0]!.id, qs[2]!.id]); // once each
  for (const q of [qs[0]!, qs[2]!]) {
    expect(arrived.find((i) => i.ref_id === q.id)!.content_version).toBe(before.find((i) => i.ref_id === q.id)!.content_version);
  }
  expect((await read(week1)).item_list.map((i) => i.ref_id)).toEqual([qs[1]!.id]);
});
