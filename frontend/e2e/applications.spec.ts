import { readFileSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { navTo, chooseJob, expect, test, type Page } from "./fixtures";

// The application tracker against the real API: recorded facts, pointer and keyboard moves,
// history, DST-safe interview times, links, drafts that are never sent, privacy.

test.use({ permissions: ["clipboard-read", "clipboard-write"] });

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })), where).toEqual([]);
}

async function signUpNurse(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`apps-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

const column = (page: Page, name: string) => page.getByRole("list", { name: "Applications by stage" }).getByRole("listitem", { name: new RegExp(`^${name}`) });

test("track an application from saved to interviewing, with history, events, links and a draft that's never sent", async ({ page, browser }) => {
  page.on("dialog", (d) => void d.accept());
  await signUpNurse(page);
  await navTo(page, "Applications");
  await expect(page.getByText("No applications yet")).toBeVisible();

  // Record one. A double click still creates one.
  await page.getByRole("button", { name: "Add an application" }).click();
  const form = page.getByRole("form", { name: "New application" });
  await form.getByLabel("Role title").fill("Ward nurse");
  await form.getByLabel("Employer").fill("Mercy General");
  await form.getByLabel(/^Next action/).first().fill("Ask about the start date");
  await form.getByRole("button", { name: "Add application" }).dblclick();
  await expect(column(page, "Saved").getByRole("link", { name: "Ward nurse" })).toHaveCount(1);
  await page.getByRole("button", { name: "Add an application" }).click();
  const second = page.getByRole("form", { name: "New application" });
  await second.getByLabel("Role title").fill("Practice nurse");
  await second.getByLabel("Employer").fill("Hill Clinic");
  await second.getByRole("button", { name: "Add application" }).click();
  await axe(page, "applications board");

  // Pointer: drag to Applied. Keyboard: the menu, to Interviewing.
  await column(page, "Saved").getByRole("link", { name: "Ward nurse" }).locator("..").dragTo(column(page, "Applied"));
  await expect(column(page, "Applied").getByRole("link", { name: "Ward nurse" })).toBeVisible();
  await page.getByLabel("Move Ward nurse at Mercy General to").selectOption("interviewing");
  await expect(column(page, "Interviewing").getByRole("link", { name: "Ward nurse" })).toBeVisible();

  // The list view, sorted, survives a reload.
  await page.locator(".segmented__option", { hasText: "List" }).click();
  await expect(page.getByRole("radio", { name: "List" })).toBeChecked();
  await page.getByRole("button", { name: "Role", exact: true }).click();
  await page.getByRole("button", { name: "Role", exact: true }).click();
  await page.reload();
  await expect(page.getByRole("columnheader", { name: "Role" })).toHaveAttribute("aria-sort", "ascending");
  const firstRow = page.getByRole("table").getByRole("row").nth(1);
  await expect(firstRow).toContainText("Practice nurse");
  await page.getByRole("link", { name: "Ward nurse" }).click();

  // History, with a correction and a rename that doesn't rewrite it.
  await expect(page.getByRole("heading", { level: 1, name: "Ward nurse" })).toBeVisible();
  const stage = page.getByRole("form", { name: "Change the stage" });
  await stage.getByLabel("Move to").selectOption("offer");
  await stage.getByRole("button", { name: "Save stage" }).click();
  await stage.getByLabel("Move to").selectOption("interviewing");
  await stage.getByLabel(/This corrects a mistake/).check();
  await stage.getByRole("button", { name: "Save stage" }).click();
  await expect(page.locator(".stage-history li").first()).toContainText("Offer → Interviewing");
  await expect(page.locator(".stage-history li").first()).toContainText("Correction");
  const details = page.getByRole("form", { name: "Details" });
  await details.getByLabel("Role title").fill("Senior ward nurse");
  await details.getByRole("button", { name: "Save details" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Senior ward nurse" })).toBeVisible();
  await expect(page.locator(".stage-history li").first()).toContainText("then: Ward nurse, Mercy General");

  // An interview at 01:30 on the night the clocks go back in Chicago: CodeCoach asks which one.
  await page.getByRole("button", { name: "Add an event" }).click();
  const ev = page.getByRole("form", { name: "New event" });
  await ev.getByLabel("What").fill("Night shift interview");
  await ev.getByLabel(/^Date/).fill("2026-11-01");
  await ev.getByLabel(/^Time \(optional\)/).fill("01:30");
  await ev.getByLabel("Time zone").selectOption("America/Chicago");
  await ev.getByRole("button", { name: "Add event" }).click();
  await expect(ev.getByText(/happens twice in America\/Chicago/)).toBeVisible();
  await ev.getByLabel(/The second one/).check();
  await ev.getByRole("button", { name: "Add event" }).click();
  await expect(page.getByText(/1 Nov 2026, 01:30 America\/Chicago|Sun, 1 Nov 2026, 01:30 America\/Chicago|01:30 America\/Chicago/).first()).toBeVisible();
  await page.getByRole("button", { name: "Add an event" }).click();
  await page.getByRole("form", { name: "New event" }).getByLabel("What").fill("Second interview");
  await page.getByRole("form", { name: "New event" }).getByRole("button", { name: "Add event" }).click();
  await expect(page.locator(".event-list__item")).toHaveCount(2);
  await expect(page.getByText("Date not known yet")).toBeVisible();

  // Link a story: preparation points to it (a link, not a copy).
  const appUrl = page.url();
  await page.goto("/stories/new");
  await page.getByLabel("Title").fill("Two call lights at once");
  await page.getByRole("button", { name: "Save story" }).click();
  await expect(page).toHaveURL(/\/stories\/[0-9a-f-]+$/);
  await page.goto(appUrl);
  await page.getByRole("checkbox", { name: "Two call lights at once" }).check();
  await expect(page.getByRole("link", { name: "Review your story “Two call lights at once”" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Do a mock interview" })).toBeVisible();

  // A draft: from typed facts only, copied and downloaded, and the stage doesn't change.
  const composer = page.locator(".draft-composer");
  await composer.getByLabel(/^To/).fill("Ms Lee");
  await composer.getByLabel(/^When/).fill("on Sunday");
  await expect(composer.getByLabel(/^Draft/)).toHaveValue(/Dear Ms Lee,[\s\S]*Senior ward nurse role at Mercy General/);
  await composer.getByRole("button", { name: "Copy" }).click();
  await expect(composer.getByText(/Copied/)).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain("Thank you for your time on Sunday");
  const download = page.waitForEvent("download");
  await composer.getByRole("button", { name: "Download as text" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("thank-you-mercy-general.txt");
  expect(readFileSync((await file.path())!, "utf8")).toContain("Dear Ms Lee,");
  await page.reload();
  await expect(page.locator(".page__header .badge")).toHaveText("Interviewing");
  await axe(page, "application detail");

  // Another account can't open it.
  const url = page.url();
  const other = await browser.newContext();
  const stranger = await other.newPage();
  await signUpNurse(stranger);
  await stranger.goto(url);
  await expect(stranger.getByText(/Application not found/)).toBeVisible();
  await other.close();

  // Archive: out of the board, kept in the archive.
  await page.getByRole("button", { name: "Archive" }).click();
  await page.goto("/applications");
  await expect(page.getByRole("link", { name: "Senior ward nurse" })).toHaveCount(0);
  await page.getByLabel("Show archived").click(); // the filter is in the address; it settles a moment later
  await expect(page.getByLabel("Show archived")).toBeChecked();
  await expect(page.getByRole("link", { name: "Senior ward nurse" })).toBeVisible();
});

test("the tracker works at 320px in the light theme", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "light" })));
  await signUpNurse(page);
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto("/applications");
  await page.getByRole("button", { name: "Add an application" }).click();
  const form = page.getByRole("form", { name: "New application" });
  await form.getByLabel("Role title").fill("Community nurse");
  await form.getByLabel("Employer").fill("City Health");
  await form.getByRole("button", { name: "Add application" }).click();
  await expect(page.getByRole("link", { name: "Community nurse" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, "board at 320px, light");
  await page.getByRole("link", { name: "Community nurse" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Community nurse" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, "application at 320px, light");
});
