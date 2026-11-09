import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chooseJob, expect, test, type Page, type Route } from "./fixtures";
import { PORT_OFFSET } from "./ports";

/**
 * A guest start or registration whose reply was lost (Volume 8, prompt 6), against the real API.
 * The request reaches the server and the account is made; the reply, and the session cookie it
 * set, never reach the page. The page sends the same request once more and the server, by this
 * browser's HttpOnly anchor cookie, returns the account the first one made: one guest, not two;
 * one account and one verification email, not "email taken".
 */
const OUTBOX = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  `../../backend/e2e-outbox${PORT_OFFSET ? `-${PORT_OFFSET}` : ""}`,
);

function mailsTo(email: string): number {
  if (!fs.existsSync(OUTBOX)) return 0;
  return fs.readdirSync(OUTBOX).filter((f) => JSON.parse(fs.readFileSync(path.join(OUTBOX, f), "utf8")).to === email).length;
}

type Made = { status: number; userId: string; resumed: string | null };

/** The first create reaches the server; its reply (and the cookie it set) is lost. Every create's
 * outcome, as the server answered it, is recorded. */
function loseFirstReply(page: Page, what: "guest" | "register"): Made[] {
  const made: Made[] = [];
  void page.route(`**/api/v1/auth/${what}`, async (route: Route) => {
    const response = await route.fetch(); // the server makes the account...
    made.push({ status: response.status(), userId: ((await response.json()) as { user: { id: string } }).user.id,
      resumed: response.headers()["x-account-resumed"] ?? null });
    if (made.length > 1) return route.fulfill({ response });
    await page.context().clearCookies({ name: "cc_refresh" }); // ...its session cookie never arrives...
    await route.abort("connectionreset"); // ...and nor does its reply
  });
  return made;
}

test("a guest start whose reply was lost resumes the same guest instead of making another", async ({ page }) => {
  await page.goto("/login");
  const made = loseFirstReply(page, "guest");
  await page.getByRole("button", { name: "Continue as guest" }).click();
  await expect(page).toHaveURL(/\/welcome$/);
  expect(made).toHaveLength(2);
  expect(made[0]).toMatchObject({ status: 201, resumed: null });
  expect(made[1]).toMatchObject({ status: 200, resumed: "guest", userId: made[0]!.userId });
  // The anchor is HttpOnly: the page's scripts can't read it.
  expect(await page.evaluate(() => document.cookie)).not.toContain("cc_create");
  // Another browser has its own anchor: its guest start makes its own guest.
  const other = await page.context().browser()!.newContext({ baseURL: new URL(page.url()).origin });
  const second = await other.newPage();
  await second.goto("/login");
  const theirs = second.waitForResponse((r) => r.url().endsWith("/api/v1/auth/guest"));
  await second.getByRole("button", { name: "Continue as guest" }).click();
  const reply = await theirs;
  expect(reply.status()).toBe(201);
  expect(((await reply.json()) as { user: { id: string } }).user.id).not.toBe(made[0]!.userId);
  await other.close();
});

test("a registration whose reply was lost signs in to that account once, with one verification email", async ({ page }) => {
  const email = `lost-reply-${Date.now()}@example.com`;
  await page.goto("/register");
  const made = loseFirstReply(page, "register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "software-engineer");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
  expect(made).toHaveLength(2);
  expect(made[1]).toMatchObject({ status: 200, resumed: "register", userId: made[0]!.userId });
  await expect.poll(() => mailsTo(email)).toBe(1);
  await expect(page.getByText(/email taken|already exists/i)).toHaveCount(0);
});
