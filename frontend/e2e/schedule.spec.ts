import { readFileSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "./fixtures";

// The schedule against the real API, in a browser set to Chicago time: scheduling from a real
// activity, the daylight-saving choice, overlaps, .ics files, moving, cancelling, a time zone
// change and an in-app reminder.

test.use({ timezoneId: "America/Chicago", locale: "en-GB" });

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })), where).toEqual([]);
}

async function signUpNurse(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`sched-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

function chicago(d: Date) {
  const date = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  const time = new Intl.DateTimeFormat("en-GB", { timeZone: "America/Chicago", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(d);
  return { date, time };
}

async function scheduleFromQuestion(page: Page, qid: string, date: string, time: string) {
  await page.goto(`/careers/registered-nurse/questions/${qid}`);
  await page.getByRole("link", { name: "Add to schedule" }).click();
  await expect(page).toHaveURL(/\/schedule\?kind=question/);
  const form = page.getByRole("form", { name: "Add to schedule" });
  await form.getByLabel("Date").fill(date);
  await form.getByLabel("Start time").fill(time);
  await form.getByRole("button", { name: "Add to schedule" }).click();
  return form;
}

test("schedule real practice, around daylight saving, export it, move it, cancel it", async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
  await signUpNurse(page);
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Schedule" }).click();
  await expect(page.getByText(/uses this device's time zone, America\/Chicago/)).toBeVisible();

  // 01:30 on the night the clocks go back happens twice: CodeCoach asks.
  const form = await scheduleFromQuestion(page, "m-pressure-0", "2026-11-01", "01:30");
  await expect(form.getByText(/happens twice in America\/Chicago/)).toBeVisible();
  await form.getByLabel(/The first one \(UTC-05:00\)/).check();
  await form.getByRole("button", { name: "Add to schedule" }).click();
  await expect(page.getByText(/Added “.+” on Sun, 1 Nov 2026/)).toBeVisible();

  // An overlapping entry is explained, not moved.
  await scheduleFromQuestion(page, "m-walk-0", "2026-11-01", "01:45").then((f) => f.getByLabel(/The first one/).check().then(() => f.getByRole("button", { name: "Add to schedule" }).click()));
  await page.goto("/schedule?week=2026-11-01");
  const day = page.locator(".schedule-day").filter({ hasText: "1 Nov 2026" });
  await expect(day.locator(".schedule-entry")).toHaveCount(2);
  await expect(day.locator(".schedule-entry").first()).toContainText("01:30");
  await expect(day.getByText(/Overlaps with .*Nothing was moved/).first()).toBeVisible();
  await axe(page, "schedule week");

  // The week as a calendar file: exact UTC times, stable ids.
  const week = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download this week (.ics)" }).click();
  const ics = readFileSync((await (await week).path())!, "utf8");
  expect(ics.startsWith("BEGIN:VCALENDAR\r\n")).toBe(true);
  expect(ics).toContain("DTSTART:20261101T063000Z"); // the first 01:30 (CDT)
  expect(ics).toContain("SEQUENCE:0");
  const uid = /UID:(\S+)/.exec(ics)![1];

  // Move it: same UID, a higher SEQUENCE.
  const first = day.locator(".schedule-entry").first();
  await first.getByRole("button", { name: "Move" }).click();
  const move = first.getByRole("form", { name: "Save new time" });
  await move.getByLabel("Date").fill("2026-11-02");
  await move.getByLabel("Start time").fill("09:00");
  await move.getByRole("button", { name: "Save new time" }).click();
  await expect(day.locator(".schedule-entry")).toHaveCount(1); // 1 Nov is a Sunday: the 2nd is next week
  await page.getByRole("button", { name: "Next week" }).click();
  const nov2 = page.locator(".schedule-day").filter({ hasText: "2 Nov 2026" });
  await expect(nov2.getByText("09:00")).toBeVisible();
  const one = page.waitForEvent("download");
  await nov2.getByRole("button", { name: ".ics" }).click();
  const moved = readFileSync((await (await one).path())!, "utf8");
  expect(moved).toContain(`UID:${uid}`);
  expect(moved).toContain("SEQUENCE:1");
  expect(moved).toContain("DTSTART:20261102T150000Z"); // 09:00 CST

  // Cancel the other: hidden, but kept for a calendar to cancel too.
  await page.getByRole("button", { name: "Previous week" }).click();
  await day.locator(".schedule-entry").first().getByRole("button", { name: "Cancel" }).click();
  await expect(day.locator(".schedule-entry")).toHaveCount(0);
  await page.getByLabel("Show cancelled").click();
  await expect(day.getByText("Cancelled")).toBeVisible();

  // Travelling: show the schedule in Tokyo time; entries stay at the same moment.
  await page.getByLabel("Schedule time zone").selectOption("Asia/Tokyo");
  await page.getByRole("button", { name: "Use this time zone" }).click();
  await expect(page.getByText(/This device is set to America\/Chicago/)).toBeVisible();
  await page.goto("/schedule?week=2026-11-02");
  await expect(page.getByText("00:00 (09:00 America/Chicago)")).toBeVisible(); // 09:00 CST is midnight on the 3rd in Tokyo
});

test("an in-app reminder, only when turned on, at 320px in the light theme", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "light" })));
  await signUpNurse(page);
  const soon = chicago(new Date(Date.now() + 6 * 60_000));
  await scheduleFromQuestion(page, "m-pressure-0", soon.date, soon.time);
  await expect(page.getByText(/Added “/)).toBeVisible();
  await expect(page.locator(".reminder")).toHaveCount(0); // off by default
  const reminders = page.getByRole("form", { name: "Reminders" });
  await reminders.getByLabel("Show reminders while CodeCoach is open").check();
  await reminders.getByRole("button", { name: "Save reminders" }).click();
  const reminder = page.locator(".reminder");
  await expect(reminder).toContainText(/In [4-6] minutes:/, { timeout: 45_000 });
  await page.setViewportSize({ width: 320, height: 700 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, "schedule with a reminder at 320px, light");
  await reminder.getByRole("button", { name: "Dismiss" }).click();
  await expect(reminder).toHaveCount(0);
});
