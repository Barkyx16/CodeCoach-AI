import { navTo, chooseJob, expect, test, type BrowserContext, type Page, type Route } from "./fixtures";

// A refresh the server processed but whose answer the browser never got must not sign the user
// out, and a refresh that answers after a deliberate sign-out must not sign them back in.
// Real browser, real backend: the cookie is HttpOnly, rotated by the server, path-scoped.

const REFRESH = "**/api/v1/auth/refresh";
const heading = (page: Page) => page.getByRole("heading", { level: 1, name: /progress/i });
const signOut = (page: Page) => page.locator("header").getByRole("button", { name: "Sign out" });

async function signUp(page: Page, tag: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`${tag}-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click(); // the optional welcome
  await expect(heading(page)).toBeVisible();
}

async function refreshCookie(context: BrowserContext) {
  const cookie = (await context.cookies("http://localhost:8000/api/v1/auth/refresh")).find((c) => c.name === "cc_refresh");
  expect(cookie, "the browser holds a refresh cookie").toBeDefined();
  return cookie!;
}

/**
 * Let the server process this refresh (it rotates the cookie), then make sure the browser still
 * holds the cookie it had before, as if the answer never arrived.
 */
async function processButKeepOldCookie(route: Route, context: BrowserContext) {
  const before = await refreshCookie(context);
  const response = await route.fetch();
  expect(response.status(), "the server accepted the refresh").toBe(200);
  await context.addCookies([before]);
  return response;
}

/**
 * Treat the access token this tab holds right now as expired: History requests that carry it get
 * a 401, so the page refreshes in the background, and requests with the new token go through.
 * Keyed on the token rather than "the first request", because in development React can cancel
 * that first request when it remounts the page.
 */
async function expireCurrentToken(page: Page) {
  let expired: string | null = null;
  await page.route((url) => url.pathname === "/api/v1/me/activity", (route) => {
    const auth = route.request().headers()["authorization"] ?? "";
    expired ??= auth;
    return auth === expired
      ? route.fulfill({
        status: 401, contentType: "application/json",
        json: { error: { code: "invalid_token", message: "Your session has expired.", request_id: "e2e", details: null } },
      })
      : route.continue();
  });
}

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((r) => { resolve = r; });
  return { promise, resolve };
}

test("a lost refresh answer: the next load recovers the same session instead of signing out", async ({ page, context }) => {
  await signUp(page, "lost-refresh");
  const original = (await refreshCookie(context)).value;
  const lost = deferred();
  await page.route(REFRESH, async (route) => {
    await processButKeepOldCookie(route, context);
    await route.abort("connectionreset"); // the answer is lost
    lost.resolve();
  }, { times: 1 });
  await page.reload(); // this load's refresh is processed by the server, but its answer is lost
  await lost.promise;
  // Not signed out: the page couldn't hear back, so it says it needs a connection.
  await expect(page.getByRole("heading", { level: 1, name: "This page needs a connection" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Sign in" })).toHaveCount(0);

  await page.reload(); // the next load presents the old cookie again, with the same attempt key
  await expect(heading(page)).toBeVisible();
  await expect(page).toHaveURL(/\/dashboard$/);
  expect((await refreshCookie(context)).value).not.toBe(original);
  await page.reload(); // and the recovered session carries on normally
  await expect(heading(page)).toBeVisible();
});

test("reloading while a refresh is still waiting for its answer keeps the user signed in", async ({ page, context }) => {
  await signUp(page, "reload-refresh");
  const processed = deferred();
  await page.route(REFRESH, async (route) => {
    await processButKeepOldCookie(route, context);
    processed.resolve();
    // No answer: the page reloads first.
  }, { times: 1 });
  await page.reload();
  await processed.promise;
  await page.reload();
  await expect(heading(page)).toBeVisible();
  await expect(page).toHaveURL(/\/dashboard$/);
});

async function loseRefreshAndCloseTab(page: Page, context: BrowserContext) {
  const processed = deferred();
  await page.route(REFRESH, async (route) => {
    await processButKeepOldCookie(route, context);
    processed.resolve();
    await route.abort("connectionreset");
  }, { times: 1 });
  await page.reload();
  await processed.promise;
  await page.close();
}

test("another tab finishes a refresh that a closed tab never heard back from", async ({ page, context }) => {
  await signUp(page, "tabs-refresh");
  const other = await context.newPage();
  await other.goto("/dashboard");
  await expect(heading(other)).toBeVisible();
  await loseRefreshAndCloseTab(page, context); // processed by the server, answer lost, tab closed

  // The other tab's access token is turned down, so it refreshes with the old cookie.
  await expireCurrentToken(other);
  const refreshed = other.waitForResponse(REFRESH);
  const listed = other.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/me/activity" && r.status() === 200);
  await navTo(other, "History");
  expect((await refreshed).status()).toBe(200); // recovered with the closed tab's attempt key
  await listed; // and the turned-down request went through on the retry
  await expect(signOut(other)).toBeVisible();
  await other.reload();
  await expect(signOut(other)).toBeVisible();
});

test("a tab that reloads can still finish a closed tab's refresh", async ({ page, context }) => {
  await signUp(page, "tabs-reload");
  const other = await context.newPage();
  await other.goto("/dashboard");
  await expect(heading(other)).toBeVisible();
  await loseRefreshAndCloseTab(page, context);
  await other.reload(); // a full page load: only what the tab stored for itself survives
  await expect(heading(other)).toBeVisible();
  await expect(other).toHaveURL(/\/dashboard$/);
});

test("two tabs loading at the same moment both stay signed in", async ({ page, context }) => {
  await signUp(page, "two-tabs");
  const other = await context.newPage();
  await Promise.all([page.goto("/dashboard"), other.goto("/dashboard")]);
  await expect(heading(page)).toBeVisible();
  await expect(heading(other)).toBeVisible();
  await Promise.all([page.reload(), other.reload()]);
  await expect(heading(page)).toBeVisible();
  await expect(heading(other)).toBeVisible();
});

test("a refresh that answers after signing out doesn't sign the user back in", async ({ page, context }) => {
  await signUp(page, "logout-refresh");
  const processed = deferred();
  const release = deferred();
  await page.route(REFRESH, async (route) => {
    const response = await processButKeepOldCookie(route, context);
    processed.resolve();
    await release.promise; // the answer is slow to arrive...
    await route.fulfill({ response }); // ...and comes after the sign-out, new cookie and all
  }, { times: 1 });
  // An expired access token makes the page refresh in the background.
  await expireCurrentToken(page);
  await navTo(page, "History");
  await processed.promise;

  await signOut(page).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(signOut(page)).toHaveCount(0);
  const late = page.waitForResponse(REFRESH);
  release.resolve();
  await late;
  // The late answer is ignored in the page, and the server ended its session too.
  await expect(page.getByRole("link", { name: "Sign in" }).first()).toBeVisible();
  await expect(signOut(page)).toHaveCount(0);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
});
