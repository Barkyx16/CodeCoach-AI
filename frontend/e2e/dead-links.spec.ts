import { chooseJob, expect, test, type Page } from "./fixtures";

/**
 * Links that lead nowhere (Volume 9, prompt 5), against the real API, each opened directly in a
 * fresh browser context: another account's note, a mistyped one, a bookmarked interview that
 * isn't there, a signed-out visitor, a removed scenario, and a temporary read failure. Private
 * records get the same generic words and the learner's own list; nothing of the owner's shows.
 */
async function signUp(page: Page, tag: string, password = "CorrectHorse42"): Promise<string> {
  const email = `${tag}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  return email;
}
const main = (page: Page) => page.locator("#main");

test("private links that lead nowhere: the same words for another account's and a mistyped record, a way forward, no loop", async ({ page, browser }) => {
  await signUp(page, "dl-owner");
  await page.goto("/careers/registered-nurse/questions/e-time-0");
  const panel = page.getByRole("region", { name: "Notes" });
  await panel.getByRole("button", { name: "Add a note" }).click();
  await panel.getByLabel("Title").fill("Owner's private handover");
  await panel.getByLabel("Note", { exact: true }).fill("Only the owner should ever read this.");
  await expect(panel.locator(".note-status")).toHaveText("Saved");
  await panel.getByRole("link", { name: "Open in your notebook" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Owner's private handover" })).toBeVisible();
  const noteUrl = new URL(page.url()).pathname;

  // Signed out, in a fresh browser: sign in first; then the link is checked for that account.
  const fresh = await browser.newContext();
  const visitor = await fresh.newPage();
  await signUp(visitor, "dl-other");
  await visitor.context().clearCookies(); // the session ends: signed out
  await visitor.goto(noteUrl);
  await expect(visitor).toHaveURL(/\/login/);
  await fresh.close();

  // Another account, in a fresh browser: the generic words, its own notebook, nothing of the owner's.
  const strangerContext = await browser.newContext();
  const stranger = await strangerContext.newPage();
  await signUp(stranger, "dl-stranger");
  await stranger.goto(noteUrl);
  await expect(stranger.getByRole("heading", { level: 1, name: "This note isn't available" })).toBeVisible();
  const theirs = await main(stranger).innerText();
  expect(theirs).not.toContain("Owner's private handover");
  expect(theirs).not.toContain("Only the owner");
  // A mistyped id reads exactly the same.
  await stranger.goto("/notes/00000000-0000-0000-0000-000000000000");
  await expect(stranger.getByRole("heading", { level: 1, name: "This note isn't available" })).toBeVisible();
  expect(await main(stranger).innerText()).toBe(theirs);
  await main(stranger).getByRole("link", { name: "Your notebook" }).click();
  await expect(stranger).toHaveURL(/\/notes$/);

  // A bookmarked interview that isn't there leads to their interviews.
  await stranger.goto("/interviews/00000000-0000-0000-0000-000000000000");
  await expect(stranger.getByRole("heading", { level: 1, name: "This interview isn't available" })).toBeVisible();
  await expect(main(stranger).getByRole("button", { name: "Try again" })).toHaveCount(0);
  await main(stranger).getByRole("link", { name: "All your interviews" }).click();
  await expect(stranger).toHaveURL(/\/history\?type=interview/);

  // A temporary failure isn't "missing": Try again works once the server answers.
  // Busy until the learner tries again (the app's own automatic retries of a read also fail).
  let busy = true;
  await page.route("**/api/v1/me/notes/*", (route) => {
    if (route.request().method() === "GET" && busy) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: { code: "server_busy", message: "The server is very busy right now.", request_id: "r" } }) });
    }
    return route.continue();
  });
  await page.goto(noteUrl);
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await expect(page.getByText(/isn't available/)).toHaveCount(0);
  busy = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Owner's private handover" })).toBeVisible();
  await strangerContext.close();
});

test("public content that's gone leads to its library", async ({ page }) => {
  await page.goto("/scenarios/no-such-scenario");
  await expect(page.getByRole("heading", { level: 1, name: "This scenario isn't available" })).toBeVisible();
  await main(page).getByRole("link", { name: "Browse scenarios" }).click();
  await expect(page).toHaveURL(/\/scenarios$/);
  await page.goto("/learn/no-such-lesson");
  await expect(page.getByRole("heading", { level: 1, name: "This lesson isn't available" })).toBeVisible();
  await page.goto("/problems/no-such-problem");
  await expect(page.getByRole("heading", { level: 1, name: "This problem isn't available" })).toBeVisible();
  await expect(main(page).getByRole("link", { name: "Browse coding problems" })).toHaveAttribute("href", "/problems?career=software-engineer");
});
