import AxeBuilder from "@axe-core/playwright";

import { chooseJob, expect, setTheme, test, type Page } from "./fixtures";

/**
 * Story freshness (Volume 12, prompt 8; docs/STORY_FRESHNESS.md), against the real API: a story is
 * linked to a requirement and chosen for a kit; a tag changes nothing; new words ask for a review
 * in both places, shown side by side. Keeping is recorded; a version that moved on while reviewing
 * is said, never used; refreshing is the learner's button. Synthetic data.
 */
const JD = `Registered Nurse - Emergency Department
Responsibilities:
- Perform patient assessment and triage for incoming patients
- Educate patients and families before discharge`;
const REQ = "Perform patient assessment and triage for incoming patients";
const TITLE = "Two call lights at once";

async function scan(page: Page, what: string) {
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const r = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(r.violations.map((v) => v.id), `${what}, ${theme}`).toEqual([]);
  }
}

async function editStory(page: Page, url: string, edit: (p: Page) => Promise<void>) {
  await page.goto(url);
  await edit(page);
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText(/^Saved as version \d+\.$/)).toBeVisible();
}

test("a story behind a kit and a requirement link: reviewed side by side, kept or refreshed only when asked", async ({ page, context }) => {
  page.on("dialog", (d) => void d.accept());
  await page.goto("/register");
  await page.getByLabel("Email").fill(`fresh-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // A story, linked to a requirement in a job target.
  await page.goto("/targets");
  await page.getByRole("button", { name: "Add a target role" }).first().click();
  await page.getByLabel("Role title").fill("ED nurse");
  await page.getByLabel("Job description").fill(JD);
  await page.getByRole("button", { name: "Find requirements" }).click();
  await expect(page).toHaveURL(/\/targets\/[0-9a-f-]+$/);
  const targetUrl = page.url();
  await page.getByRole("button", { name: "Add an example" }).click();
  await page.getByLabel("Short title").fill(TITLE);
  await page.getByLabel("Situation (optional)").fill("Two patients rang at once on a night shift.");
  await page.getByLabel("What you did (optional)").fill("I checked who was at higher risk first.");
  await page.getByLabel("Result (optional)").fill("Both were seen within five minutes.");
  await page.getByRole("checkbox", { name: REQ }).check();
  await page.getByRole("button", { name: "Save example" }).click();
  await page.getByRole("link", { name: "Open in your story bank" }).click();
  await expect(page).toHaveURL(/\/stories\/[0-9a-f-]+$/);
  const storyUrl = page.url();

  // ...chosen for an interview kit.
  await page.goto("/applications");
  await page.getByRole("button", { name: "Add an application" }).click();
  const form = page.getByRole("form", { name: "New application" });
  await form.getByLabel("Role title").fill("ED nurse");
  await form.getByLabel("Employer").fill("Synthetic Hospital");
  await form.getByRole("button", { name: "Add application" }).click();
  await page.getByRole("link", { name: "ED nurse" }).click();
  await page.getByRole("button", { name: "Add an event" }).click();
  const ev = page.getByRole("form", { name: "New event" });
  await ev.getByLabel("What").fill("Panel interview");
  await ev.getByLabel(/^Date/).fill("2026-11-12");
  await ev.getByRole("button", { name: "Add event" }).click();
  await page.getByRole("link", { name: "Interview-day kit" }).click();
  // The application page has its own story checkboxes: wait for the kit before ticking.
  await expect(page).toHaveURL(/\/kit$/);
  await expect(page.getByRole("button", { name: "Save kit" })).toBeVisible();
  const kitUrl = page.url();
  await page.getByRole("checkbox", { name: TITLE }).check();
  await expect(page.getByRole("checkbox", { name: TITLE })).toBeChecked();
  await expect(page.getByRole("button", { name: "Save kit" })).toBeEnabled();
  await page.getByRole("button", { name: "Save kit" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();

  // A tag only: nothing to review.
  await editStory(page, storyUrl, async (p) => { await p.getByLabel(/^Skill tags/).fill("triage"); });
  await page.goto(kitUrl);
  await expect(page.getByRole("checkbox", { name: TITLE })).toBeChecked();
  await expect(page.getByText(/The story changed since/)).toHaveCount(0);

  // New words: asked in both places, side by side.
  await editStory(page, storyUrl, async (p) => { await p.getByLabel("Result", { exact: true }).fill("Both were seen within five minutes and the family was told."); });
  await page.goto(kitUrl);
  const kitReview = page.locator(".freshness").filter({ hasText: TITLE });
  await expect(kitReview).toContainText("The story changed since you chose it for this kit (version 1, now 3). Review whether it still fits.");
  await expect(kitReview.getByRole("row", { name: /Result Both were seen within five minutes\. Both were seen within five minutes and the family was told\./ })).toBeVisible();
  await expect(page.getByRole("article", { name: "Your interview pack" })).toContainText(`${TITLE} (version 1; the story has changed since)`);
  await scan(page, "kit review");

  // Keep it as prepared: recorded, and not asked again.
  await kitReview.getByRole("button", { name: "Keep version 1" }).click();
  await expect(page.getByText(`Kept “${TITLE}” as you prepared it.`)).toBeVisible();
  await page.reload();
  await expect(page.locator(".freshness").filter({ hasText: TITLE })).toContainText("You kept version 1 on ");

  // Changed again; another tab moves it on while this one reviews: said, not used.
  await editStory(page, storyUrl, async (p) => { await p.getByLabel("Result", { exact: true }).fill("Both were seen within five minutes; I told the family."); });
  await page.goto(kitUrl);
  await expect(page.locator(".freshness").filter({ hasText: TITLE })).toContainText("changed again since you kept version 1 (now version 4)");
  const other = await context.newPage();
  await editStory(other, storyUrl, async (p) => { await p.getByLabel("Result", { exact: true }).fill("Both were seen within five minutes; I told the family and documented it."); });
  await other.close();
  await page.locator(".freshness").filter({ hasText: TITLE }).getByRole("button", { name: "Use version 4 in this kit" }).click();
  await expect(page.getByText(/now version 5; you reviewed version 4/)).toBeVisible();
  await page.locator(".freshness").filter({ hasText: TITLE }).getByRole("button", { name: "Use version 5 in this kit" }).click();
  await expect(page.getByText(`This kit now uses version 5 of “${TITLE}”.`)).toBeVisible();
  await expect(page.locator(".freshness")).toHaveCount(0);

  // The requirement link: its own review, apart from the requirement's own version.
  await page.goto(targetUrl);
  const linkReview = page.locator(".experience").filter({ hasText: TITLE });
  await expect(linkReview).toContainText(`For “${REQ}”:`);
  await expect(linkReview).toContainText("The story changed since you linked it (version 1, now 5). Review whether it still fits.");
  await expect(linkReview).toContainText("Linked to the current wording (version 1)");
  await scan(page, "link review");
  await linkReview.getByRole("button", { name: "Use version 5 for these links" }).click();
  await expect(linkReview.locator(".freshness")).toHaveCount(0);
  await page.reload();
  await expect(page.locator(".experience").filter({ hasText: TITLE }).locator(".freshness")).toHaveCount(0);
});
