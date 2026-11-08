import { chooseJob, expect, test, type Browser, type Page } from "./fixtures";

/**
 * Two devices for one account (separate browser contexts: separate storage, separate sessions)
 * and a third context for a different account. Server work appears on both devices; browser-only
 * drafts stay on the device that wrote them and are cleared when it signs out; an older device's
 * edit is held back, not saved over the newer one; the other account sees nothing. Synthetic
 * accounts. docs/PERSISTENCE.md has the per-feature table.
 */
const PASSWORD = "CorrectHorse42";
const QUESTION = "/careers/registered-nurse/questions/e-time-0";

async function signUp(page: Page, email: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function signIn(browser: Browser, email: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
  return page;
}

const privateKeys = (page: Page) =>
  page.evaluate(() => Object.keys(localStorage).filter((k) => /answer|draft|round|retry|capture|interview-message/.test(k)));

test("two devices, one account, and a stranger: what syncs, what stays, what's held back", async ({ page, browser }) => {
  const email = `devices-${Date.now()}@example.com`;
  await signUp(page, email);

  // Device 1: a note (server) and an unsent answer draft (this browser only).
  await page.goto("/notes/new");
  await page.getByLabel("Title").fill("Written on device one");
  await page.getByLabel("Note", { exact: true }).fill("first version");
  await expect(page.locator(".note-status")).toHaveText("Saved");
  await expect(page).toHaveURL(/\/notes\/[\w-]+$/);
  const noteUrl = new URL(page.url()).pathname;
  await page.goto(QUESTION);
  await page.getByLabel("Your answer", { exact: true }).fill("An unsent draft on device one");
  await expect(page.getByText("Draft saved on this device, not sent yet.")).toBeVisible();

  // Device 2, same account: the note is there; device one's draft isn't (it was never sent).
  const second = await signIn(browser, email);
  await second.goto("/notes");
  await expect(second.getByRole("link", { name: "Written on device one" })).toBeVisible();
  await second.goto(QUESTION);
  await expect(second.getByLabel("Your answer", { exact: true })).toHaveValue("");

  // Both devices open the note; device 2 saves first; device 1's older edit is held back.
  await second.goto(noteUrl);
  await page.goto(noteUrl);
  await expect(page.getByLabel("Note", { exact: true })).toHaveValue("first version");
  await second.getByLabel("Note", { exact: true }).fill("newer, from device two");
  await expect(second.locator(".note-status")).toHaveText("Saved");
  await page.getByLabel("Note", { exact: true }).fill("older, from device one");
  const conflict = page.getByRole("region", { name: "Edit conflict" });
  await expect(conflict).toContainText("newer, from device two");
  await expect(conflict).toContainText("older, from device one");
  await second.reload();
  await expect(second.getByLabel("Note", { exact: true })).toHaveValue("newer, from device two"); // not overwritten

  // A different account: nothing of this one's, even with the note's address.
  const strangerPage = await (await browser.newContext()).newPage();
  await signUp(strangerPage, `stranger-${Date.now()}@example.com`);
  await strangerPage.goto("/notes");
  await expect(strangerPage.getByRole("link", { name: "Written on device one" })).toHaveCount(0);
  await strangerPage.goto(noteUrl);
  await expect(strangerPage.getByText("Note not found")).toBeVisible();
  await strangerPage.goto(QUESTION);
  await expect(strangerPage.getByLabel("Your answer", { exact: true })).toHaveValue("");

  // Signing out on device 1 clears its private drafts (after the warning), and the server's
  // copy is still there when it signs back in.
  await page.goto("/dashboard");
  expect((await privateKeys(page)).length).toBeGreaterThan(0);
  page.once("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: "Sign out" }).first().click();
  await expect(page).toHaveURL(/\/$/);
  expect(await privateKeys(page)).toEqual([]);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
  await page.goto(noteUrl);
  await expect(page.getByLabel("Note", { exact: true })).toHaveValue("newer, from device two");
});

test("with storage unavailable, the page says a draft can't be kept instead of implying it is", async ({ browser }) => {
  const context = await browser.newContext();
  await context.addInitScript(() => {
    const blocked = () => {
      throw new DOMException("blocked", "QuotaExceededError");
    };
    Storage.prototype.setItem = blocked;
  });
  const page = await context.newPage();
  await signUp(page, `nostorage-${Date.now()}@example.com`);
  await page.goto(QUESTION);
  await page.getByLabel("Your answer", { exact: true }).fill("Typed with storage blocked");
  await expect(page.getByText(/couldn't be saved on this device/)).toBeVisible();
  await expect(page.getByText("Draft saved on this device, not sent yet.")).toHaveCount(0);
});
