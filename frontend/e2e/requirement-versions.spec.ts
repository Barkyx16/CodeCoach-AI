import AxeBuilder from "@axe-core/playwright";

import { chooseJob, expect, setTheme, test, type Page } from "./fixtures";

/**
 * Versioned requirements (Volume 12, prompt 5; docs/REQUIREMENT_VERSIONS.md), against the real
 * API: a nurse links a story to a requirement, rewords the requirement (and tidies another), sees
 * the change summary with the story it affects before saving, then the story says it was linked to
 * an earlier wording until it's deliberately reused; the history keeps both versions; a second tab's
 * stale save is refused with both sets shown and its edits kept. Synthetic data.
 */
const JD = `Registered Nurse - Medical Ward

Responsibilities:
- Perform patient assessment and triage for incoming patients
- Administer medications and monitor patient responses

Requirements
- Current RN license
- 2+ years of acute care experience`;

async function noViolations(page: Page, view: string) {
  await expect(page.locator(".spinner")).toHaveCount(0, { timeout: 15_000 });
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(scan.violations.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(", ")}`), `${view}, ${theme}`).toEqual([]);
  }
}

test("a reworded requirement keeps its history, and a story says it was linked to the earlier wording", async ({ page, context }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`versions-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto("/targets");
  await page.getByRole("button", { name: "Add a target role" }).first().click();
  await page.getByLabel("Role title").fill("Ward Nurse");
  await page.getByLabel("Job description").fill(JD);
  await page.getByRole("button", { name: "Find requirements" }).click();
  await expect(page).toHaveURL(/\/targets\/[0-9a-f-]+$/);
  const url = page.url();

  // A story linked to the licence requirement.
  await page.getByRole("button", { name: "Add an example" }).click();
  const form = page.getByRole("form", { name: "New example" });
  await form.getByLabel("Short title").fill("Night shift escalation");
  await form.getByLabel("Current RN license").check();
  await form.getByRole("button", { name: "Save example" }).click();
  const story = page.getByText(/Shows “Current RN license”/).locator("xpath=ancestor::li[1]");
  await expect(story).toContainText("Linked to the current wording (version 1)");

  // Reword it and tidy another; nothing is saved until the changes are reviewed.
  await page.getByRole("button", { name: "Edit requirements" }).click();
  const editor = page.getByRole("region", { name: "Edit the requirements" });
  const fields = editor.getByRole("textbox");
  const texts = await fields.evaluateAll((els) => els.map((e) => (e as HTMLInputElement).value));
  const licence = texts.indexOf("Current RN license");
  const experience = texts.indexOf("2+ years of acute care experience");
  expect(licence).toBeGreaterThanOrEqual(0);
  expect(experience).toBeGreaterThanOrEqual(0);
  await fields.nth(licence).fill("Current RN license and BLS certification");
  await fields.nth(experience).fill("2+ years of acute care experience.");
  await editor.getByRole("button", { name: "Review changes" }).click();
  const review = editor.getByRole("region", { name: "Changes to save" });
  await expect(review).toContainText(new RegExp(`^1 changed, 0 added, 0 removed, ${texts.length - 1} unchanged`));
  await expect(review.getByText(/Changed \(a new version\)/).locator("xpath=ancestor::li[1]")).toContainText("version 1 → 2");
  await expect(review).toContainText("Stories linked to it: Night shift escalation.");
  await expect(review).toContainText("Wording tidied (the same requirement and version)");
  await noViolations(page, "change review");

  // A second tab saves a different change first.
  const second = await context.newPage();
  await second.goto(url);
  await second.getByRole("button", { name: "Edit requirements" }).click();
  const other = second.getByRole("region", { name: "Edit the requirements" });
  const otherFields = other.getByRole("textbox");
  await otherFields.nth(texts.indexOf("Administer medications and monitor patient responses")).fill("Give medications safely and monitor responses");
  await other.getByRole("button", { name: "Review changes" }).click();
  const savedOther = second.waitForResponse((r) => /\/requirements$/.test(r.url()) && r.request().method() === "PUT");
  await other.getByRole("button", { name: "Save these changes" }).click();
  expect((await savedOther).ok()).toBe(true);

  // This tab's save is now stale: refused, both sets shown, these edits kept.
  await review.getByRole("button", { name: "Save these changes" }).click();
  const stale = editor.getByRole("alert");
  await expect(stale).toContainText("Nothing was saved");
  await expect(stale).toContainText("Give medications safely and monitor responses");
  await expect(fields.nth(licence)).toHaveValue("Current RN license and BLS certification");
  await stale.getByRole("button", { name: "Keep mine and review again" }).click();
  await editor.getByRole("button", { name: "Review changes" }).click();
  // Reviewed against the saved set: the other tab's change would be undone by keeping these words.
  await expect(review).toContainText(/^2 changed/);
  const saved = page.waitForResponse((r) => /\/requirements$/.test(r.url()) && r.request().method() === "PUT");
  await review.getByRole("button", { name: "Save these changes" }).click();
  expect((await saved).ok()).toBe(true);

  // After a reload: the story points at the earlier wording; the history keeps both versions.
  await page.reload();
  const reworded = page.getByRole("article", { name: "Current RN license and BLS certification" });
  await expect(reworded).toBeVisible();
  const storyAfter = page.getByText(/Shows “Current RN license and BLS certification”/).locator("xpath=ancestor::li[1]");
  await expect(storyAfter).toContainText("Linked to an earlier wording (version 1; now version 2)");
  await reworded.getByText("History (version 2)").click();
  await expect(reworded).toContainText("Version 1, before the first change: “Current RN license”");
  await expect(reworded).toContainText("Version 2, changed: “Current RN license and BLS certification”");
  await expect(page.getByRole("article", { name: "2+ years of acute care experience." })).toContainText("History");
  await noViolations(page, "target with versions");

  // Reusing the story for the new wording is deliberate, and recorded as a reuse.
  await storyAfter.getByRole("button", { name: "Use it for the current wording" }).click();
  await expect(storyAfter).toContainText("Reused for the current wording (version 2, first linked to version 1)");
  await second.reload();
  await expect(second.getByText(/Shows “Current RN license and BLS certification”/).locator("xpath=ancestor::li[1]"))
    .toContainText("Reused for the current wording (version 2, first linked to version 1)");
});
