import { expect, test, type APIRequestContext, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * A session that ends by itself mid-work (Volume 8, prompt 8), against the real API. Ada's session
 * is revoked elsewhere (sign out everywhere) while she has unsaved code in the editor; her next
 * request finds out. The code stays on screen, the banner offers a sign-in that comes back here,
 * and nothing she started is sent again. Signing back in as Ada brings the code back; signing in
 * as Bea shows Bea's own, while Ada's stays locked to Ada on this device until she returns.
 */
const PASSWORD = "CorrectHorse42";
const MARK = "// Ada was here before her session ended";

async function account(request: APIRequestContext, tag: string): Promise<{ email: string; id: string }> {
  const email = `lapse-${tag}-${Date.now()}@example.com`;
  const r = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD } });
  expect(r.status()).toBe(201);
  return { email, id: ((await r.json()) as { user: { id: string } }).user.id };
}

async function signInHere(page: Page, email: string) {
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
}

/** Somewhere else, Ada signs out of every device: this tab's tokens stop working. */
async function revokeEverywhere(request: APIRequestContext, email: string) {
  const r = await request.post(`${API_URL}/api/v1/auth/login`, { data: { email, password: PASSWORD } });
  const { access_token } = (await r.json()) as { access_token: string };
  expect((await request.post(`${API_URL}/api/v1/auth/logout-all`, { headers: { Authorization: `Bearer ${access_token}` } })).status()).toBe(204);
}

async function editorText(page: Page): Promise<string> {
  return ((await page.locator(".monaco-editor .view-lines").first().textContent()) ?? "").replace(/\u00a0/g, " ");
}

/** Ada types in the workspace, then her session is revoked and her next request finds out. */
async function adaLapsesMidEdit(page: Page, request: APIRequestContext, ada: { email: string }) {
  const hints: string[] = [];
  page.on("request", (r) => { if (r.url().endsWith("/api/v1/ai/hint")) hints.push(r.method()); });
  await page.goto("/login");
  await signInHere(page, ada.email);
  await expect(page).not.toHaveURL(/\/login$/);
  await page.goto("/problems/two-sum");
  const editor = page.locator(".monaco-editor").first();
  await editor.click();
  await page.keyboard.press("ControlOrMeta+End");
  await page.keyboard.press("Enter");
  await page.keyboard.insertText(MARK); // one input: typed key by key, the editor's suggestions take some
  await expect(page.getByText("Saved on device")).toBeVisible();
  await revokeEverywhere(request, ada.email);
  await page.getByRole("button", { name: "Get a hint" }).click();
  await expect(page.getByText("Your session ended. Please sign in again.")).toBeVisible();
  // Still on screen (the page reloads its data once the session's is dropped, so read until it settles).
  await expect.poll(() => editorText(page)).toContain(MARK);
  return hints;
}

test("the same account signs back in and carries on with the code that was on screen", async ({ page, request }) => {
  const ada = await account(request, "ada");
  const hints = await adaLapsesMidEdit(page, request, ada);
  await expect(page.getByText(/Unsaved work this page keeps on this device stays with the account that was signed in/)).toBeVisible();
  await page.getByRole("link", { name: "Sign in again" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await signInHere(page, ada.email);
  await expect(page).toHaveURL(/\/problems\/two-sum$/);
  await expect.poll(() => editorText(page)).toContain(MARK);
  await expect(page.getByText("Your session ended. Please sign in again.")).toHaveCount(0);
  expect(hints).toEqual(["POST"]); // the hint that met the ended session isn't asked again by itself
});

test("another account signing in sees its own code; Ada's stays locked to Ada until she returns", async ({ page, request }) => {
  const ada = await account(request, "ada2");
  const bea = await account(request, "bea");
  await adaLapsesMidEdit(page, request, ada);
  await page.getByRole("link", { name: "Sign in again" }).click();
  await signInHere(page, bea.email);
  await expect(page).toHaveURL(/\/problems\/two-sum$/);
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await expect.poll(() => editorText(page)).toContain("public int[] twoSum");
  expect(await editorText(page)).not.toContain(MARK);
  const kept = await page.evaluate(([a, b]) => ({
    ada: localStorage.getItem(`codecoach.draft.v1.${a}.two-sum`), bea: localStorage.getItem(`codecoach.draft.v1.${b}.two-sum`),
  }), [ada.id, bea.id]);
  expect(kept.ada).toContain(MARK);
  expect(kept.bea).toBeNull();
  // Bea signs out on purpose (her own work is cleared, not Ada's); Ada signs in and has hers back.
  await page.goto("/settings");
  await page.getByRole("region", { name: "Sign out" }).getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/login");
  await signInHere(page, ada.email);
  await expect(page).not.toHaveURL(/\/login$/);
  await page.goto("/problems/two-sum");
  await expect.poll(() => editorText(page)).toContain(MARK);
});
