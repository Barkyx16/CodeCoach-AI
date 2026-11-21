import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { chooseJob, expect, test, type Page } from "./fixtures";

// One connected journey through this batch, against the real API (synthetic data only): a recorded
// interview, preparation kept relative to it, a reschedule previewed and confirmed (with a stale
// preview refused first), a draft from explicitly chosen context, and a version 2 export checked by
// the real validator. Nothing is sent anywhere.

const BACKEND = fileURLToPath(new URL("../../backend", import.meta.url));
const PYTHON = process.env.PYTHON ?? "python";

async function signUp(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`journey-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function moveInterview(page: Page, date: string) {
  await page.locator(".event-list__item").first().getByRole("button", { name: "Edit" }).click();
  const form = page.getByRole("form", { name: "Edit event" });
  await form.getByLabel(/^Date/).fill(date);
  await form.getByRole("button", { name: "Save event" }).click();
  await expect(page.getByRole("form", { name: "Edit event" })).toHaveCount(0);
}

test("prep follows a rescheduled interview only when confirmed; a draft and a linked export, end to end", async ({ page, context }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "one desktop run is enough for this journey");
  await signUp(page);

  // A recorded interview with an exact time.
  await page.goto("/applications");
  await page.getByRole("button", { name: "Add an application" }).click();
  const form = page.getByRole("form", { name: "New application" });
  await form.getByLabel("Role title").fill("Ward nurse");
  await form.getByLabel("Employer").fill("Synthetic Hospital");
  await form.getByRole("button", { name: "Add application" }).click();
  await page.getByRole("link", { name: "Ward nurse" }).click();
  const appUrl = page.url();
  await page.getByRole("button", { name: "Add an event" }).click();
  const ev = page.getByRole("form", { name: "New event" });
  await ev.getByLabel("What").fill("Panel interview");
  await ev.getByLabel(/^Date/).fill("2026-12-15");
  await ev.getByLabel(/^Time \(optional\)/).fill("10:00");
  await ev.getByLabel("Time zone").selectOption("Europe/London");
  await ev.getByRole("button", { name: "Add event" }).click();

  // Preparation two days before, then kept relative to the interview (a fixed time by default).
  await page.getByRole("link", { name: "Schedule preparation time" }).click();
  const add = page.getByRole("form", { name: "Add to schedule" });
  await add.getByLabel("Date").fill("2026-12-13");
  await add.getByLabel("Start time").fill("18:00");
  // Wait for the server to have it: going to another page straight after the click could cancel
  // the request (an isolated full run once loaded the week before the entry existed).
  const created = page.waitForResponse((r) => r.url().endsWith("/api/v1/me/schedule") && r.request().method() === "POST");
  await add.getByRole("button", { name: "Add to schedule" }).click();
  expect((await created).status()).toBe(201);
  await expect(page.getByText(/^Added “Prepare: Panel interview/)).toBeVisible();
  await page.goto("/schedule?week=2026-12-13");
  const entry = page.locator(".schedule-entry").filter({ hasText: "Prepare: Panel interview" });
  await expect(entry.getByText(/A fixed time: it stays here if the interview moves/)).toBeVisible();
  await entry.getByRole("button", { name: "Keep it relative to the interview" }).click();
  await expect(entry.getByText(/Kept relative to the interview/)).toBeVisible();
  const before = (await entry.locator(".schedule-entry__time").innerText()).trim();

  // The interview moves a day later; the preview proposes, nothing moves yet.
  await page.goto(appUrl);
  await moveInterview(page, "2026-12-16");
  await page.getByText("Preparation times").click();
  const tick = page.getByRole("checkbox", { name: /Prepare: Panel interview .*→/ });
  await expect(tick).not.toBeChecked();

  // Another tab moves the interview again after this preview: confirming moves nothing.
  const other = await context.newPage();
  await other.goto(appUrl);
  await expect(other.getByRole("heading", { level: 1, name: "Ward nurse" })).toBeVisible();
  await moveInterview(other, "2026-12-17");
  await other.close();
  await tick.check();
  await page.getByRole("button", { name: "Move selected (1)" }).click();
  await expect(page.getByText(/changed again since this preview\. Nothing was moved/)).toBeVisible();
  // The refreshed preview, confirmed.
  await page.getByRole("checkbox", { name: /Prepare: Panel interview .*→/ }).check();
  await page.getByRole("button", { name: "Move selected (1)" }).click();
  await expect(page.getByText("Moved 1.")).toBeVisible();
  await page.goto("/schedule?week=2026-12-15"); // two days before the interview, now on the 17th
  const moved = page.locator(".schedule-entry").filter({ hasText: "Prepare: Panel interview" });
  await expect(moved).toBeVisible();
  expect((await moved.locator(".schedule-entry__time").innerText()).trim()).toBe(before); // same clock time (no DST in between)
  await expect(page.locator(".schedule-day").filter({ hasText: "Prepare: Panel interview" })).toContainText(/15/); // two days before the 17th

  // A draft from context chosen explicitly; edits survive a change of details.
  await page.goto(appUrl);
  const composer = page.locator(".draft-composer");
  await composer.getByRole("combobox", { name: "Interview" }).selectOption({ index: 1 }); // the recorded interview
  const draft = composer.getByLabel(/^Draft/);
  await expect(draft).toHaveValue(/Thank you for your time on .*17.* talking with me about the Ward nurse role at Synthetic Hospital\./);
  await draft.press("End");
  await draft.pressSequentially(" Thanks again.");
  await composer.getByLabel(/^To/).fill("Ms Lee");
  await expect(draft).toHaveValue(/Thanks again\.$/);
  await expect(composer.getByText(/The details behind this draft changed since you edited it/)).toBeVisible();

  // The linked export, downloaded through the page and checked by the real validator.
  await page.goto("/settings");
  await page.getByRole("checkbox", { name: /Include links between records/ }).check();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download my data" }).click()]);
  const file = testInfo.outputPath("codecoach-data-v2.json");
  await download.saveAs(file);
  const doc = JSON.parse(readFileSync(file, "utf8")) as {
    export_version: number;
    schedule: { entries: { kind: string; follows_interview_from: string | null; links: { activity: { state: string } } }[] };
    applications: { id: string; events: { id: string }[] }[];
  };
  expect(doc.export_version).toBe(2);
  const prep = doc.schedule.entries.find((e) => e.kind === "application_event")!;
  expect(prep.follows_interview_from).toMatch(/^2026-12-17T10:00:00/);
  expect(prep.links.activity.state).toBe("present");
  const out = execFileSync(PYTHON, ["-m", "app.cli", "check-export", file], { cwd: BACKEND, encoding: "utf8" });
  expect(out).toContain("No problems found.");
});
