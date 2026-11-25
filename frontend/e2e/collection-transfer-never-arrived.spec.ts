import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * A copy or move that never reached the server, offered again after a reload (Volume 20, prompt 5),
 * against the real API. The request is stopped before it reaches the server; after a reload the page
 * asks the server what its key made (nothing), names what it was for from the ids this device kept,
 * and Send again moves each item once, with the request's own key. Synthetic account.
 */
test("a move stopped before the server, a reload, then Send again with its own key", async ({ page, request }) => {
  const email = `mvn-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
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
  const week1 = await make("Week 1", [qs[0]!.id, qs[1]!.id, qs[2]!.id]);
  const week2 = await make("Week 2", [qs[3]!.id]);
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
  const keys: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/items/transfer")) keys.push((r.postDataJSON() as { client_request_id: string }).client_request_id);
  });
  await page.route("**/items/transfer", (route) => route.abort("connectionreset")); // never reaches the server
  await form.getByRole("button", { name: "Move 2 to “Week 2”" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "No reply came" })).toBeVisible();
  await page.unroute("**/items/transfer");
  const read = async (id: string) =>
    ((await (await request.get(`${API_URL}/api/v1/me/collections/${id}`, { headers: auth })).json()) as { item_list: { ref_id: string }[] }).item_list.map((i) => i.ref_id).sort();
  expect(await read(week2)).toEqual([qs[3]!.id]); // nothing happened on the server

  await page.reload();
  const panel = page.locator(".earlier-action");
  await expect(panel).toContainText(/The move you sent at .* never arrived\./);
  await expect(panel).toContainText("It was a move of 2 items to “Week 2”. All of them are still in this collection.");
  await panel.getByRole("button", { name: "Send again: move 2 items to “Week 2”" }).click();
  const outcomes = page.getByRole("region", { name: "What happened: moving to “Week 2”" });
  await expect(outcomes.getByRole("status")).toHaveText("2 moved. Nothing needs attention.");
  expect(keys).toHaveLength(2);
  expect(keys[1]).toBe(keys[0]); // its own key
  expect(await read(week2)).toEqual([qs[0]!.id, qs[2]!.id, qs[3]!.id].sort());
  expect(await read(week1)).toEqual([qs[1]!.id]);
  // Each once: the other collection holds no copy twice.
  expect(new Set(await read(week2)).size).toBe(3);
});
