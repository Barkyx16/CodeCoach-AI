import { chooseJob, expect, test, type Browser, type Page } from "./fixtures";

/**
 * A real two-device conflict on one story (two browser contexts for one synthetic account): the
 * older device's save is refused, both versions are shown side by side, and each choice keeps
 * exactly what it promises. Nothing is merged; nothing is lost. docs/PERSISTENCE.md, "What
 * Saved means" and "Conflict policy".
 */
const PASSWORD = "CorrectHorse42";

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

test("two devices edit one story: the older save is refused, both versions shown, the chosen one kept", async ({ page: a, browser }) => {
  const email = `save-state-${Date.now()}@example.com`;
  await signUp(a, email);
  await a.goto("/stories/new");
  await a.getByLabel("Title").fill("Two call lights at once");
  await a.getByLabel("Result").fill("Both patients were seen.");
  await a.getByRole("button", { name: "Save story" }).click();
  await expect(a).toHaveURL(/\/stories\/[0-9a-f-]+$/);
  const url = a.url().replace(/^https?:\/\/[^/]+/, "");

  // Both devices have version 1 open.
  const b = await signIn(browser, email);
  await b.goto(url);
  await expect(b.getByLabel("Result")).toHaveValue("Both patients were seen.");

  // A saves first.
  await a.getByLabel("Result").fill("Both patients were seen within five minutes (device A).");
  await a.getByRole("button", { name: "Save changes" }).click();
  await expect(a.getByText("Saved as version 2.")).toBeVisible();

  // B, still on version 1, saves its own edit: refused, both versions shown, B's text untouched.
  await b.getByLabel("Result").fill("Both were seen; I escalated the second (device B).");
  await b.getByRole("button", { name: "Save changes" }).click();
  const conflict = b.getByRole("region", { name: "Edit conflict" });
  await expect(conflict.getByRole("alert")).toContainText("This story was saved in another tab or on another device (version 2");
  await expect(conflict).toContainText("Both were seen; I escalated the second (device B).");
  await expect(conflict).toContainText("Both patients were seen within five minutes (device A).");
  await expect(b.getByLabel("Result")).toHaveValue("Both were seen; I escalated the second (device B).");

  // B keeps its version: it becomes version 3, and A sees it after a reload. A's version is kept
  // in the story's history (every version is), not lost.
  await conflict.getByRole("button", { name: "Keep mine as the newest version" }).click();
  await expect(b.getByText("Saved as version 3.")).toBeVisible();
  await expect(conflict).toHaveCount(0);
  await a.reload();
  await expect(a.getByLabel("Result")).toHaveValue("Both were seen; I escalated the second (device B).");
  await a.getByRole("button", { name: "Version 2" }).click();
  await expect(a.getByText("Both patients were seen within five minutes (device A).")).toBeVisible();
});
