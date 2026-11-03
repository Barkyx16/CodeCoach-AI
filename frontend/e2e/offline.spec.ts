import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

// The installable app and offline mode, against the production build (`vite preview`, port 4173)
// and the real backend. "Offline" is Playwright's network emulation for the whole browser context.

const ANSWER = "When a patient's vitals drop I check airway, breathing and circulation first, call the rapid response team and give an SBAR handoff.";

async function signUpNurse(page: Page, tag: string): Promise<string> {
  const email = `${tag}-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click(); // the optional welcome
  await expect(page).toHaveURL(/\/dashboard$/);
  return email;
}

async function serviceWorkerReady(page: Page) {
  await page.waitForFunction(async () => {
    const registration = await navigator.serviceWorker.getRegistration();
    return Boolean(registration?.active) && navigator.serviceWorker.controller !== null;
  }, null, { timeout: 30_000 });
}

/** Every URL in every Cache Storage cache this origin has. */
async function cachedUrls(page: Page): Promise<Record<string, string[]>> {
  return page.evaluate(async () => {
    const out: Record<string, string[]> = {};
    for (const name of await caches.keys()) {
      out[name] = (await (await caches.open(name)).keys()).map((r) => r.url);
    }
    return out;
  });
}

async function saveForOffline(page: Page) {
  const panel = page.getByRole("region", { name: "Offline" });
  await panel.getByRole("button", { name: "Save for offline" }).click();
  await expect(panel.getByText(/Saved on this device/)).toBeVisible();
}

// Playwright's offline emulation doesn't reliably stop requests that a service worker passes
// through to the network, so the API is also refused at the routing layer while "offline"
// (a real offline device can't reach the server at all).
const API = "http://localhost:8000/**";
async function goOffline(context: BrowserContext, page: Page) {
  await context.route(API, (route) => route.abort("internetdisconnected"));
  await context.setOffline(true);
  await page.evaluate(() => window.dispatchEvent(new Event("offline")));
}
async function goOnline(context: BrowserContext) {
  await context.unroute(API);
  await context.setOffline(false);
}

test("saved content and drafts work offline, uncached pages say so, and nothing private is cached", async ({ page, context }) => {
  await page.goto("/");
  await serviceWorkerReady(page);
  await signUpNurse(page, "offline");

  await page.goto("/learn/rn-sbar-handoff");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await saveForOffline(page);
  await page.goto("/careers/registered-nurse/questions/m-walk-0");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await saveForOffline(page);
  await page.getByRole("textbox", { name: "Your answer" }).fill(ANSWER);
  await expect(page.getByText("Draft saved on this device, not sent yet.")).toBeVisible();
  await page.goto("/problems/two-sum");
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await saveForOffline(page);
  // Visit private pages too, so their API responses would show up below if anything cached them.
  for (const path of ["/dashboard", "/history", "/notes"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  }

  const cacheMap = await cachedUrls(page);
  const all = Object.values(cacheMap).flat();
  expect(all.length).toBeGreaterThan(10);
  expect(all.filter((u) => u.includes("/api/") || u.startsWith("http://localhost:8000")), "no API response is cached").toEqual([]);
  const saved = await page.evaluate(async () => {
    const cache = await caches.open("codecoach-offline-v1");
    const out: string[] = [];
    for (const r of await cache.keys()) out.push(await (await cache.match(r))!.text());
    return out;
  });
  expect(saved).toHaveLength(3);
  for (const body of saved) {
    expect(body).not.toContain("@example.com");
    expect(body).not.toMatch(/"best_score":\s*\d/); // the public copy, never a personal one
  }

  // Offline: a fresh load is served by the cached shell.
  await goOffline(context, page);
  await page.goto("/careers/registered-nurse/questions/m-walk-0");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText("You're offline.", { exact: false }).first()).toBeVisible();
  await expect(page.locator(".header__user .badge")).toHaveText("Offline");
  await expect(page.getByRole("textbox", { name: "Your answer" })).toHaveValue(ANSWER); // still this account's draft
  await expect(page.getByRole("button", { name: "Get feedback" })).toBeDisabled();
  await expect(page.getByText(/Feedback needs a connection; your draft stays on this device/)).toBeVisible();

  await page.goto("/learn/rn-sbar-handoff");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText(/Checking your answers needs a connection/)).toBeVisible();

  await page.goto("/problems/two-sum");
  await expect(page.getByRole("heading", { name: "Two Sum", level: 1 })).toBeVisible();
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await expect(page.getByText(/Running and judging need the server/)).toBeVisible();
  await expect(page.getByRole("button", { name: /^(Submit|Save attempt)/ })).toBeDisabled();

  await page.goto("/careers/registered-nurse/questions/e-good-0"); // never saved
  await expect(page.getByText(/This page isn't saved on this device/)).toBeVisible();
  await page.goto("/history"); // account data
  await expect(page.getByRole("heading", { level: 1, name: "This page needs a connection" })).toBeVisible();

  // A new tab, launched with no network at all.
  const cold = await context.newPage();
  await cold.goto("/offline");
  await expect(cold.getByRole("heading", { level: 1, name: "Saved for offline" })).toBeVisible();
  await expect(cold.getByRole("listitem").filter({ hasText: "Two Sum" })).toBeVisible();
  await expect(cold.getByText(/3 of up to 50 items/)).toBeVisible();
  await new AxeBuilder({ page: cold }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze()
    .then((r) => expect(r.violations.map((v) => v.id)).toEqual([]));
  await cold.close();

  // Back online: the session is checked again (the account page loads by itself) and the draft
  // can be sent; nothing was sent for us.
  await goOnline(context);
  await expect(page.getByRole("heading", { level: 1, name: "History" })).toBeVisible();
  await page.goto("/careers/registered-nurse/questions/m-walk-0");
  await expect(page.locator(".header__user .badge")).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Your answer" })).toHaveValue(ANSWER);
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: "Feedback" })).toBeVisible();
});

test("a note edited offline syncs on reconnect, and an edit made elsewhere becomes a choice", async ({ page, context, browser }) => {
  await page.goto("/");
  await serviceWorkerReady(page);
  const email = await signUpNurse(page, "notes-offline");
  await page.goto("/notes/new");
  await page.getByLabel("Title").fill("Escalation");
  await page.getByLabel("Note", { exact: true }).fill("Call early.");
  await expect(page.locator(".note-status")).toHaveText("Saved");
  await expect(page).toHaveURL(/\/notes\/[0-9a-f-]{36}$/);
  const noteUrl = page.url();

  await goOffline(context, page);
  await page.getByLabel("Note", { exact: true }).fill("Call early. Use SBAR.");
  await expect(page.locator(".note-status")).toContainText("Sync pending");
  await goOnline(context);
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect(page.locator(".note-status")).toHaveText("Saved");

  // Meanwhile on another device: the same account edits the note while this one is offline.
  await goOffline(context, page);
  await page.getByLabel("Note", { exact: true }).fill("Call early. Use SBAR. Document it.");
  await expect(page.locator(".note-status")).toContainText("Sync pending");
  const otherDevice = await browser.newContext({ baseURL: "http://localhost:4173" });
  const other = await otherDevice.newPage();
  await other.goto("/login");
  await other.getByLabel("Email").fill(email);
  await other.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await other.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await other.waitForURL(/dashboard|verify/);
  await other.goto(noteUrl);
  await other.getByLabel("Note", { exact: true }).fill("Written on my phone.");
  await expect(other.locator(".note-status")).toHaveText("Saved");
  await otherDevice.close();

  await goOnline(context);
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  const conflict = page.getByRole("region", { name: "Edit conflict" });
  await expect(conflict).toBeVisible();
  await expect(conflict.getByText("Written on my phone.")).toBeVisible();
  await expect(conflict.getByText("Call early. Use SBAR. Document it.")).toBeVisible();
});

test("signing out deletes this account's drafts from the device; the next account sees none", async ({ page }) => {
  page.on("dialog", (d) => { expect(d.message()).toMatch(/1 unsent draft on this device/); void d.accept(); });
  await signUpNurse(page, "shared-device-a");
  await page.goto("/careers/registered-nurse/questions/m-walk-0");
  await page.getByRole("textbox", { name: "Your answer" }).fill(ANSWER);
  await expect(page.getByText("Draft saved on this device, not sent yet.")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/$/);
  const left = await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("codecoach.answer.") || k === "codecoach.device-user.v1"));
  expect(left).toEqual([]);
  page.removeAllListeners("dialog");
  await signUpNurse(page, "shared-device-b");
  await page.goto("/careers/registered-nurse/questions/m-walk-0");
  await expect(page.getByRole("textbox", { name: "Your answer" })).toHaveValue("");
});

test("when the draft can't be kept on the device, the page says so and leaving asks first", async ({ page }) => {
  await page.addInitScript(() => {
    const setItem = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key: string, value: string) {
      if (key.startsWith("codecoach.answer.")) throw new DOMException("Quota exceeded", "QuotaExceededError");
      return setItem.call(this, key, value);
    };
  });
  await signUpNurse(page, "storage-full");
  await page.goto("/careers/registered-nurse/questions/m-walk-0");
  await page.getByRole("textbox", { name: "Your answer" }).fill(ANSWER);
  await expect(page.getByRole("alert").filter({ hasText: "couldn't be saved on this device" })).toBeVisible();
  await expect(page.getByText("Draft saved on this device")).toHaveCount(0);
  let asked = false;
  page.on("dialog", (d) => { asked = d.type() === "beforeunload"; void d.dismiss(); });
  await page.close({ runBeforeUnload: true }); // closing the tab
  await expect.poll(() => asked).toBe(true);
  expect(page.isClosed()).toBe(false); // the learner chose to stay
  await expect(page.getByRole("textbox", { name: "Your answer" })).toHaveValue(ANSWER);
});

test("an update waits for the learner, and updating keeps the draft", async ({ page }) => {
  const swPath = resolve(process.cwd(), "dist/sw.js"); // Playwright runs from frontend/
  const original = readFileSync(swPath, "utf8");
  try {
    await page.goto("/");
    await serviceWorkerReady(page);
    await signUpNurse(page, "update");
    await page.goto("/careers/registered-nurse/questions/m-walk-0");
    await page.getByRole("textbox", { name: "Your answer" }).fill(ANSWER);
    await page.evaluate(() => { (window as unknown as { marker: number }).marker = 1; });

    writeFileSync(swPath, `${original}\n// a new release\n`);
    await page.evaluate(async () => { await (await navigator.serviceWorker.getRegistration())?.update(); });
    const banner = page.getByRole("status").filter({ hasText: "A new version of CodeCoach is ready" });
    await expect(banner).toBeVisible({ timeout: 20_000 });
    // Nothing happened on its own: same page, same draft.
    expect(await page.evaluate(() => (window as unknown as { marker?: number }).marker)).toBe(1);
    await expect(page.getByRole("textbox", { name: "Your answer" })).toHaveValue(ANSWER);

    await banner.getByRole("button", { name: "Update now" }).click();
    await page.waitForFunction(() => (window as unknown as { marker?: number }).marker === undefined, null, { timeout: 20_000 });
    await expect(page.getByRole("textbox", { name: "Your answer" })).toHaveValue(ANSWER);
    await expect(page.getByRole("status").filter({ hasText: "A new version" })).toHaveCount(0);
  } finally {
    writeFileSync(swPath, original);
  }
});

test("@mobile manifest, icons and an offline launch on a phone-sized screen", async ({ page, context }) => {
  const manifest = await (await page.request.get("/manifest.webmanifest")).json() as { icons: { src: string; sizes: string; purpose: string }[]; display: string; start_url: string };
  expect(manifest.display).toBe("standalone");
  expect(manifest.icons.map((i) => `${i.sizes}:${i.purpose}`)).toEqual(["192x192:any", "512x512:any", "512x512:maskable"]);
  for (const icon of manifest.icons) {
    const res = await page.request.get(icon.src);
    expect(res.status()).toBe(200);
    expect(res.headers()["content-type"]).toContain("image/png");
  }
  await page.goto("/learn/rn-sbar-handoff");
  await serviceWorkerReady(page);
  await saveForOffline(page);
  await goOffline(context, page);
  await page.goto("/learn/rn-sbar-handoff");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText("You're offline.", { exact: false }).first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await goOnline(context);
});
