import AxeBuilder from "@axe-core/playwright";
import { chooseJob, expect, test, type Page } from "./fixtures";

// The interview-day kit against the real API: built from a recorded interview, edited and kept,
// printed with only what was chosen, and private to its owner.

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })), where).toEqual([]);
}

async function signUpNurse(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`kit-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function interview(page: Page) {
  await page.goto("/applications");
  await page.getByRole("button", { name: "Add an application" }).click();
  const form = page.getByRole("form", { name: "New application" });
  await form.getByLabel("Role title").fill("Ward nurse");
  await form.getByLabel("Employer").fill("Mercy General");
  await form.getByRole("button", { name: "Add application" }).click();
  await page.getByRole("link", { name: "Ward nurse" }).click();
  await page.getByRole("button", { name: "Add an event" }).click();
  const ev = page.getByRole("form", { name: "New event" });
  await ev.getByLabel("What").fill("Panel interview");
  await ev.getByLabel(/^Date/).fill("2026-11-12");
  await ev.getByRole("button", { name: "Add event" }).click();
  await page.getByRole("link", { name: "Interview-day kit" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Panel interview" })).toBeVisible();
}

test("prepare an interview day, keep it, and print only what was chosen", async ({ page, browser }) => {
  await signUpNurse(page);
  await page.goto("/stories/new");
  await page.getByLabel("Title").fill("Two call lights at once");
  await page.getByLabel("Short version (about a minute)").fill("Two patients rang at once; I triaged by risk and asked a colleague to help.");
  await page.getByRole("button", { name: "Save story" }).click();
  await expect(page).toHaveURL(/\/stories\/[0-9a-f-]+$/);
  await interview(page);

  // Useful straight away: suggestions, labelled.
  await expect(page.getByRole("checkbox", { name: "Find out whether it's remote, by phone or in person" })).toBeVisible();
  await page.getByRole("combobox", { name: /^Format/ }).selectOption("remote");
  await page.getByRole("textbox", { name: /^Meeting link/ }).fill("https://meet.example.com/abc?pwd=secret");
  await page.getByRole("button", { name: "Add an interviewer" }).click();
  await page.getByLabel("Role", { exact: true }).fill("Ward manager");
  await page.getByRole("button", { name: "Save kit" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Check your microphone and camera" })).toBeVisible(); // remote suggestions now
  await expect(page.getByRole("link", { name: "mock interview setup" })).toBeVisible();

  // Make it yours: tick, hide, reorder by keyboard, exclude, add, choose a story.
  await page.getByRole("checkbox", { name: "Confirm the date, time and time zone" }).check();
  await page.getByRole("button", { name: /^Hide “Find a quiet place/ }).click();
  await page.getByRole("button", { name: /Move “What are the next steps after this interview\?” up/ }).press("Enter");
  await page.getByLabel("Add your own question").fill("How is feedback given to new nurses?");
  await page.locator("form").filter({ has: page.getByLabel("Add your own question") }).getByRole("button", { name: "Add" }).click();
  await page.getByRole("checkbox", { name: "Two call lights at once" }).check();
  await page.getByRole("button", { name: "Save kit" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("checkbox", { name: "Confirm the date, time and time zone" })).toBeChecked();
  await expect(page.getByText(/Hidden: Find a quiet place/)).toBeVisible();
  const before = page.getByRole("region", { name: "Before the interview" });
  await expect(before.getByRole("link", { name: "Two call lights at once" })).toBeVisible();
  await expect(before).toContainText("How is feedback given to new nurses?");
  await axe(page, "interview kit");

  // Print: only the pack, without the meeting link until chosen.
  const pack = page.getByRole("article", { name: "Your interview pack" });
  await expect(pack).toContainText("Not sent to anyone");
  await expect(pack).not.toContainText("meet.example.com");
  await expect(pack).toContainText("Two call lights at once: Two patients rang at once");
  await page.emulateMedia({ media: "print" });
  await expect(pack).toBeVisible();
  await expect(page.getByRole("button", { name: "Save kit" })).toBeHidden();
  await expect(page.locator("header.header")).toBeHidden();
  await page.emulateMedia({ media: "screen" });
  await page.getByRole("checkbox", { name: "Meeting link (private)" }).check();
  await expect(pack).toContainText("meet.example.com/abc?pwd=secret");

  // Someone else can't open it.
  const url = page.url();
  const other = await browser.newContext();
  const stranger = await other.newPage();
  await signUpNurse(stranger);
  await stranger.goto(url);
  await expect(stranger.getByRole("heading", { level: 1, name: "This interview kit isn't available" })).toBeVisible(); // the same words as a deleted one
  await other.close();

  // Back to the application it came from.
  await page.getByRole("link", { name: /Back to the application/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Ward nurse" })).toBeVisible();
});

test("the kit at 320px in the light theme keeps private notes folded", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "light" })));
  await signUpNurse(page);
  await page.setViewportSize({ width: 320, height: 700 });
  await interview(page);
  await expect(page.locator("details").filter({ hasText: "Private notes" })).not.toHaveAttribute("open", "");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, "kit at 320px, light");
});
