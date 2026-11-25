import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * A copy or move whose reply was lost, then a reload (Volume 19, prompt 1), against the real API.
 * The key was kept on this device before sending, so after the reload the page asks the server what
 * it made (a read) and shows the first reply's outcomes, "2 moved", with nothing sent again; and the
 * dashboard's "Waiting for a reply" can check it too. Synthetic accounts.
 */
async function setUp(page: import("@playwright/test").Page, request: import("@playwright/test").APIRequestContext) {
  const email = `mvr-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
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
  // Move two, and lose the reply after the server has moved them.
  await page.goto(`/saved/collections/${week1}`);
  for (const q of [qs[0]!, qs[2]!]) await page.getByRole("checkbox", { name: `Select: ${q.title}` }).check();
  await page.getByRole("button", { name: "Move 2 to…" }).click();
  const form = page.getByRole("form", { name: "Move 2 items to another collection" });
  await form.getByLabel("To collection").selectOption({ label: "Week 2 (1 item)" });
  const posts: string[] = [];
  page.on("request", (r) => { if (r.method() === "POST" && r.url().endsWith("/items/transfer")) posts.push(r.url()); });
  await page.route("**/items/transfer", async (route) => {
    await route.fetch();
    await route.abort("connectionreset");
  });
  await form.getByRole("button", { name: "Move 2 to “Week 2”" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "No reply came" })).toBeVisible();
  await page.unroute("**/items/transfer");
  return { week1, week2, qs, posts, auth };
}

test("after a reload, the page says what the lost move did, and sends nothing again", async ({ page, request }) => {
  const { week1, week2, qs, posts, auth } = await setUp(page, request);
  await page.reload();
  const notice = page.locator(".earlier-action");
  await expect(notice).toContainText(/Your copy or move from .* arrived\./);
  await expect(notice).toContainText("These are what it did, and nothing was done twice.");
  const outcomes = page.getByRole("region", { name: "What happened: moving to “Week 2”" });
  await expect(outcomes.getByRole("status")).toHaveText("2 moved. Nothing needs attention.");
  await expect(outcomes).toContainText(qs[0]!.title);
  await expect(page.getByRole("link", { name: "Open “Week 2”" })).toHaveAttribute("href", `/saved/collections/${week2}`);
  expect(posts).toHaveLength(1);
  const read = async (id: string) =>
    ((await (await request.get(`${API_URL}/api/v1/me/collections/${id}`, { headers: auth })).json()) as { item_list: { ref_id: string }[] }).item_list.map((i) => i.ref_id);
  expect(await read(week2)).toEqual([qs[3]!.id, qs[0]!.id, qs[2]!.id]); // each once
  expect(await read(week1)).toEqual([qs[1]!.id]);
  // Asked once: after another reload there's nothing left to ask about.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Week 1" })).toBeVisible();
  await expect(page.locator(".earlier-action")).toHaveCount(0);
});

test("the dashboard's Waiting for a reply checks it without sending it again", async ({ page, request }) => {
  const { week2, posts } = await setUp(page, request);
  await page.goto("/dashboard");
  const waiting = page.getByRole("region", { name: "Continue your work" }).getByRole("group", { name: "Waiting for a reply" });
  await expect(waiting).toContainText("Copy or move between collections");
  await waiting.getByRole("button", { name: "Check result" }).click();
  await expect(waiting).toContainText("It arrived.");
  await expect(waiting.getByRole("link", { name: "Open the other collection" })).toHaveAttribute("href", `/saved/collections/${week2}`);
  expect(posts).toHaveLength(1);
});
