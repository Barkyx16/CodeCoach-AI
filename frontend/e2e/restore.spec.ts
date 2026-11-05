import { readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { chooseJob, expect, test, type Page } from "./fixtures";

// Restore against the real API with synthetic accounts only: download a real backup from one
// account, preview and restore it into another, restore it again (nothing added), edit one
// restored note, remove the batch (the edit stays), and a tampered file that can't make anyone
// an admin or invent results. Then phone-sized and dark.

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })), where).toEqual([]);
}

async function signUp(page: Page, tag: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`${tag}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function signOut(page: Page) {
  await page.locator("header").getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("link", { name: "Sign in" }).first()).toBeVisible();
}

test("download a backup, restore it into another account, restore again, edit, then remove the batch", async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
  await signUp(page, "source");
  // A note, written the normal way (from a question's notes panel; it autosaves).
  await page.goto("/careers/registered-nurse/questions/e-time-0");
  const panel = page.getByRole("region", { name: "Notes" });
  await panel.getByRole("button", { name: "Add a note" }).click();
  await panel.getByLabel("Title").fill("Handover tips");
  await panel.getByLabel("Note", { exact: true }).fill("SBAR, then questions.");
  await expect(panel.locator(".note-status")).toHaveText("Saved");
  await page.goto("/settings");
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download my data" }).click()]);
  const file = join(tmpdir(), `backup-${Date.now()}.json`);
  writeFileSync(file, readFileSync((await download.path())!));
  await signOut(page);

  await signUp(page, "restored");
  await page.goto("/settings");
  await page.getByRole("link", { name: "Restore from a backup" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Restore from a backup" })).toBeVisible();
  await page.getByLabel("Backup file").setInputFiles(file);
  const pv = page.getByRole("region", { name: "2. Check what would be added" });
  await expect(pv).toContainText("came from a different account");
  await expect(pv.getByRole("checkbox", { name: "Notes: 1 new" })).toBeChecked();
  await pv.getByText(/Not restored from this file/).click();
  await expect(pv).toContainText("submissions");
  await axe(page, "restore preview");
  await pv.getByRole("button", { name: /^Restore / }).click();
  await expect(page.getByText(/Restored: 1 notes/)).toBeVisible();

  // The same file again adds nothing.
  await page.getByLabel("Backup file").setInputFiles(file);
  await expect(page.getByText("You've restored from this file before. Records already here will be skipped.")).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Notes: 0 new" })).toBeDisabled();

  // Edit the restored note, then remove the batch: the edited note stays.
  await page.goto("/notes");
  await page.getByRole("link", { name: "Handover tips" }).click();
  await page.getByLabel("Note", { exact: true }).fill("SBAR, then questions. My own edit.");
  await expect(page.locator(".note-status")).toHaveText("Saved");
  await page.goto("/settings/restore");
  await page.getByRole("button", { name: "Remove what this added" }).click();
  await expect(page.getByText(/kept 1 you'd changed since/)).toBeVisible();
  await page.goto("/notes");
  await expect(page.getByRole("link", { name: "Handover tips" })).toBeVisible();
});

test("a tampered file can't grant a role or invent results; works at 320px in dark", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "dark" })));
  await signUp(page, "tamper");
  await page.setViewportSize({ width: 320, height: 720 });
  const file = join(tmpdir(), `tampered-${Date.now()}.json`);
  writeFileSync(file, JSON.stringify({
    export_version: 1,
    profile: { id: "someone-else", is_admin: true, email: "admin@example.com" },
    submissions: [{ problem: "two-sum", status: "accepted" }],
    notes: [{ title: "Kept", body: "Only this comes in." }],
  }));
  await page.goto("/settings/restore");
  await page.getByLabel("Backup file").setInputFiles(file);
  const pv = page.getByRole("region", { name: "2. Check what would be added" });
  await expect(pv.getByRole("checkbox", { name: "Notes: 1 new" })).toBeChecked();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, "restore at 320px, dark");
  await pv.getByRole("button", { name: /^Restore / }).click();
  await expect(page.getByText(/Restored: 1 notes/)).toBeVisible();
  await page.goto("/admin/reports");
  await expect(page.getByRole("heading", { name: /Content reports/ })).toHaveCount(0); // still not an admin
  await page.goto("/history");
  await expect(page.getByText("Two Sum")).toHaveCount(0); // no result was invented
});
