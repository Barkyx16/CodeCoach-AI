import AxeBuilder from "@axe-core/playwright";
import { chooseJob, expect, test, type Page } from "./fixtures";

async function signUpNurse(page: Page, tag: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`${tag}-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click(); // the optional welcome
  await expect(page).toHaveURL(/\/dashboard$/);
}

const status = (page: Page) => page.locator(".note-status");

test("capture in context, autosave, search, edit in two tabs, leave mid-save, undo delete, privacy", async ({ page, context, browser }) => {
  await signUpNurse(page, "notes");
  await page.goto("/careers/registered-nurse/questions/e-time-0");
  const panel = page.getByRole("region", { name: "Notes" });
  await panel.getByRole("button", { name: "Add a note" }).click();
  await panel.getByLabel("Title").fill("Escalate early");
  await panel.getByLabel("Note", { exact: true }).fill("Next time I should call the rapid response team sooner.\n\n<img src=x onerror=alert(1)> **bold**");
  await panel.getByLabel("Tags (comma-separated)").fill("escalation, sbar");
  await expect(panel.locator(".note-status")).toHaveText("Saved");
  await panel.getByRole("link", { name: "Open in your notebook" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Escalate early" })).toBeVisible();
  const noteUrl = page.url();
  await expect(page.getByRole("link", { name: "A time patient assessment mattered" })).toBeVisible();
  await expect(page.getByText("Copied on")).toBeVisible(); // the snapshot is labelled as a copy

  // Safe Markdown: the preview has no HTML image or script.
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.locator(".note-markdown strong")).toHaveText("bold");
  await expect(page.locator(".note-markdown img, .note-markdown script")).toHaveCount(0);
  await page.getByRole("button", { name: "Write" }).click();
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => v.id), "note page").toEqual([]);

  // Two tabs: the second one's older edit is held back and both versions are shown.
  const other = await context.newPage();
  await other.goto(noteUrl);
  await expect(other.getByLabel("Note", { exact: true })).toHaveValue(/rapid response/);
  await page.getByLabel("Note", { exact: true }).fill("Edited in tab A");
  await expect(status(page)).toHaveText("Saved");
  await other.getByLabel("Note", { exact: true }).fill("Edited in tab B");
  const conflict = other.getByRole("region", { name: "Edit conflict" });
  await expect(conflict).toContainText("Edited in tab A");
  await expect(conflict).toContainText("Edited in tab B");
  await conflict.getByRole("button", { name: "Keep my version" }).click();
  await expect(status(other)).toHaveText("Saved");
  await other.close();
  await page.reload();
  await expect(page.getByLabel("Note", { exact: true })).toHaveValue("Edited in tab B");

  // Leaving before the autosave fires still saves.
  await page.getByLabel("Note", { exact: true }).fill("Edited in tab B, then left quickly");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Notes" }).click();
  await expect(page.getByRole("heading", { name: "Your notes" })).toBeVisible();
  await expect.poll(async () => (await page.request.get("http://localhost:8000/health")).ok()).toBe(true);
  await page.goto(noteUrl);
  await expect(page.getByLabel("Note", { exact: true })).toHaveValue("Edited in tab B, then left quickly");

  // Search in the notebook; the search survives opening a note and coming Back after a reload.
  await page.goto("/notes");
  await page.getByRole("searchbox", { name: "Search notes" }).fill("left quickly");
  await expect(page.getByRole("link", { name: "Escalate early" })).toBeVisible();
  await page.getByRole("link", { name: "Escalate early" }).click();
  await page.reload();
  await page.getByRole("link", { name: "Back to your notebook" }).click();
  await expect(page).toHaveURL(/q=left\+quickly|q=left%20quickly/);
  await expect(page.getByRole("searchbox", { name: "Search notes" })).toHaveValue("left quickly");
  const listScan = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(listScan.violations.map((v) => v.id), "notes list").toEqual([]);

  // Another account can't open it.
  const stranger = await browser.newContext();
  const page2 = await stranger.newPage();
  await signUpNurse(page2, "stranger");
  await page2.goto(noteUrl);
  await expect(page2.getByText("Note not found")).toBeVisible();
  await stranger.close();

  // Delete with undo.
  await page.goto(noteUrl);
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText(/Deleted “Escalate early”/)).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).click();
  await page.getByRole("searchbox", { name: "Search notes" }).fill("");
  await expect(page.getByRole("link", { name: "Escalate early" })).toBeVisible();
});
