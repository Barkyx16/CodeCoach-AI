import { expect, test, type APIRequestContext, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Coming back to a list that changed (Volume 9, prompt 6), against the real API, on the notebook
 * (newest first, so new notes push the others down). A note is opened from far down the list;
 * then notes are added above it, it's deleted, or the learner scrolls while the list reloads. Back
 * restores by the note, not by pixels: the same note, where it was on screen, with focus; a deleted
 * one gives way to its neighbour and says so; a learner who took over is left alone. A direct visit
 * starts at the top. The filtered coding-list journey (navigation.spec.ts) is unchanged.
 */
const PASSWORD = "CorrectHorse42";

async function seeded(request: APIRequestContext, count: number): Promise<{ email: string; token: string; ids: string[] }> {
  const email = `restore-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const r = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD } });
  expect(r.status()).toBe(201);
  const token = ((await r.json()) as { access_token: string }).access_token;
  const ids: string[] = [];
  for (let i = 1; i <= count; i++) ids.push(await addNote(request, token, `Synthetic note ${String(i).padStart(2, "0")}`));
  return { email, token, ids };
}

async function addNote(request: APIRequestContext, token: string, title: string): Promise<string> {
  const r = await request.post(`${API_URL}/api/v1/me/notes`, { headers: { Authorization: `Bearer ${token}` }, data: { title, body: "Synthetic." } });
  expect(r.status()).toBe(201);
  return ((await r.json()) as { id: string }).id;
}

async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

/** Opens `title` from the notebook, scrolled into the middle of the screen; returns where it sat. */
async function openFromList(page: Page, title: string): Promise<{ href: string; top: number }> {
  await page.goto("/notes");
  const link = page.locator(".notes-list").getByRole("link", { name: title, exact: true });
  await link.evaluate((el) => el.scrollIntoView({ block: "center" }));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(300);
  const top = await link.evaluate((el) => Math.round(el.getBoundingClientRect().top));
  const href = (await link.getAttribute("href"))!;
  await link.click();
  await expect(page).toHaveURL(new RegExp(`${href}$`));
  // The note is on screen, so the list has really been left. (The address changes first; Back
  // before the note showed returned to a list that never went away, still focused on the link
  // just clicked, which a full run under load once mistook for a restore.)
  await expect(page.getByLabel("Title", { exact: true })).toHaveValue(title);
  return { href, top };
}

const focusedHref = (page: Page) => page.evaluate(() => document.activeElement?.getAttribute("href") ?? null);
const topOf = (page: Page, href: string) =>
  page.locator(`.notes-list a[href="${href}"]`).evaluate((el) => Math.round(el.getBoundingClientRect().top));

test("Back to the notebook after notes were added above, after the note was deleted, and after scrolling during the reload", async ({ page, request }) => {
  const { email, token, ids } = await seeded(request, 30);
  await signIn(page, email);

  // Added above: by pixels this would land three notes away; by the note, it's the same one.
  const first = await openFromList(page, "Synthetic note 08");
  for (const t of ["Added later A", "Added later B", "Added later C"]) await addNote(request, token, t);
  await page.goBack();
  await expect.poll(() => focusedHref(page)).toBe(first.href);
  expect(Math.abs((await topOf(page, first.href)) - first.top)).toBeLessThan(40);
  // Once per return: the learner moves away, a background refetch (the tab regains focus) doesn't
  // pull them back.
  await page.mouse.wheel(0, -5000);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThan(50);
  await page.evaluate(() => { window.dispatchEvent(new Event("focus")); document.dispatchEvent(new Event("visibilitychange")); });
  await page.waitForTimeout(500);
  expect(await page.evaluate(() => window.scrollY)).toBeLessThan(50);
  // Forward to the note and Back again is another return: restored again.
  await page.goForward();
  await expect(page).toHaveURL(new RegExp(`${first.href}$`));
  await page.goBack();
  await expect.poll(() => focusedHref(page)).toBe(first.href);

  // Deleted while away: its neighbour takes focus, and a screen reader hears why.
  const second = await openFromList(page, "Synthetic note 10");
  const deleted = ids[9]!; // "Synthetic note 10"
  expect(second.href).toBe(`/notes/${deleted}`);
  expect((await request.delete(`${API_URL}/api/v1/me/notes/${deleted}`, { headers: { Authorization: `Bearer ${token}` } })).ok()).toBe(true);
  await page.goBack();
  await expect.poll(() => focusedHref(page)).toMatch(new RegExp(`^/notes/(${ids[8]}|${ids[10]})$`)); // note 09 or 11
  await expect(page.locator("#app-announcer")).toHaveText("The item you opened isn't in this list any more.");
  await expect(page.locator(`.notes-list a[href="/notes/${deleted}"]`)).toHaveCount(0);

  // The learner scrolls while the list is still loading: it isn't snapped back.
  await openFromList(page, "Synthetic note 05");
  let release!: () => void;
  let asked!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  const reloading = new Promise<void>((resolve) => { asked = resolve; });
  await page.route(/\/api\/v1\/me\/notes\?/, async (route) => { asked(); await held; await route.continue(); });
  await page.goBack();
  // The list is back on screen (from before) and its reload is on the way: only now can the learner
  // scroll it. (A wheel sent before the page was there scrolled the note, a full run once showed.)
  await reloading;
  await expect(page.locator(".notes-list")).toBeVisible();
  // mouse.wheel returns before the page has handled the event. Wait until it has (the page moved),
  // and only then let the reload answer: releasing at once raced the handler, and on CI's slower
  // runner the answer won (run 287), so the restore ran as if nobody had scrolled.
  const before = await page.evaluate(() => window.scrollY);
  await page.mouse.wheel(0, before > 300 ? -300 : 300);
  await expect.poll(() => page.evaluate(() => window.scrollY)).not.toBe(before);
  const scrolled = await page.evaluate(() => window.scrollY);
  release();
  await expect(page.locator(".notes-list")).toBeVisible();
  await page.waitForTimeout(300); // a restore would have happened by now
  expect(await focusedHref(page)).toBeNull();
  expect(Math.abs((await page.evaluate(() => window.scrollY)) - scrolled)).toBeLessThan(5); // not snapped back
  await page.unroute(/\/api\/v1\/me\/notes\?/);

  // A direct visit is a new context: the top of the page, nothing focused in the list.
  await page.goto("/notes");
  await expect(page.locator(".notes-list")).toBeVisible();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  expect(await focusedHref(page)).toBeNull();
});
