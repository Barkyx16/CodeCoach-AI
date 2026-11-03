import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "./fixtures";

// The story bank against the real API: an example written in a job target is the same story in
// the bank; edits are versions; the writing check only proposes; practising never edits the
// story; unsaved edits survive a reload; another account can't see any of it.

const JD = `Registered Nurse, Medical Ward
Responsibilities: assess patients, prioritise care, work closely with the multidisciplinary team.`;

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })), where).toEqual([]);
}

async function signUpNurse(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`stories-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("one story, from a job target to the story bank to practice, with every version kept", async ({ page, browser }) => {
  page.on("dialog", (d) => void d.accept());
  await signUpNurse(page);

  // An example written in a job target...
  await page.goto("/targets");
  await page.getByRole("button", { name: "Add a target role" }).first().click();
  await page.getByLabel("Role title").fill("Ward nurse");
  await page.getByLabel("Job description").fill(JD);
  await page.getByRole("button", { name: "Find requirements" }).click();
  await expect(page).toHaveURL(/\/targets\/[0-9a-f-]+$/);
  await page.getByRole("button", { name: "Add an example" }).click();
  await page.getByLabel("Short title").fill("Two call lights at once");
  await page.getByLabel("Situation (optional)").fill("On a night shift two patients rang at the same time.");
  await page.getByLabel("What you did (optional)").fill("Basically I really checked who was at higher risk first. I asked a colleague to check the other patient.");
  await page.getByLabel("Result (optional)").fill("Both patients were seen within five minutes.");
  await page.getByRole("button", { name: "Save example" }).click();

  // ...is the same story in the story bank.
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Stories" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Your stories" })).toBeVisible();
  await expect(page.getByText("Not written yet: Task")).toBeVisible();
  await expect(page.getByText(/For Ward nurse/)).toBeVisible();
  await axe(page, "stories list");
  await page.getByRole("link", { name: "Two call lights at once" }).click();
  await expect(page).toHaveURL(/\/stories\/[0-9a-f-]+$/);
  const storyUrl = page.url();

  // Add what the target form doesn't have; save as version 2.
  await page.getByLabel("Task").fill("Decide who to see first.");
  await page.getByLabel("Prioritising").check();
  await page.getByLabel("Teamwork").check();
  await page.getByLabel("Notes").fill("PRIVATE: ward 7, March.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Saved as version 2.")).toBeVisible();

  // The writing check: questions, and a shorter version to accept or not. Nothing is invented.
  await page.getByRole("button", { name: "Suggest a shorter version" }).click();
  const proposal = page.getByRole("region", { name: "Suggestion for Action" });
  await expect(proposal).toContainText("I checked who was at higher risk first.");
  await proposal.getByRole("button", { name: "Use this version" }).click();
  await expect(page.getByRole("textbox", { name: "Action", exact: true })).toHaveValue("I checked who was at higher risk first. I asked a colleague to check the other patient.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Saved as version 3.")).toBeVisible();
  await page.getByRole("button", { name: "Version 3" }).click();
  await expect(page.getByText(/Edited with the writing check/)).toBeVisible();
  await axe(page, "story editor with versions");

  // Unsaved edits survive a reload, and are offered back rather than applied silently.
  await page.getByLabel("Reflection (optional)").fill("Ask for help sooner.");
  await page.reload();
  await expect(page.getByText(/You have unsaved changes to this story/)).toBeVisible();
  await page.getByRole("button", { name: "Restore them" }).click();
  await expect(page.getByLabel("Reflection (optional)")).toHaveValue("Ask for help sooner.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Saved as version 4.")).toBeVisible();

  // Practise it: a separate answer; the story stays at version 4.
  await page.goto("/careers/registered-nurse/questions/m-pressure-0");
  await page.getByText("Practise with one of your stories").click();
  await page.getByRole("radio", { name: /Two call lights at once/ }).check();
  await page.getByRole("button", { name: "Start my answer from this story" }).click();
  await expect(page.getByRole("textbox", { name: "Your answer" })).toHaveValue(/I checked who was at higher risk first/);
  await page.getByRole("button", { name: "Link this question to the story" }).click();
  await expect(page.getByText("This question is linked to the story.")).toBeVisible();
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: "Feedback", exact: true })).toBeVisible();
  await page.goto(storyUrl);
  await expect(page.getByText(/STORY BANK · VERSION 5/)).toBeVisible(); // the link is the only change
  await expect(page.getByRole("heading", { name: "Practised with this story" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Action", exact: true })).toHaveValue("I checked who was at higher risk first. I asked a colleague to check the other patient.");

  // Restore the very first version: it comes back as a new version, nothing is lost.
  await page.getByRole("button", { name: "Version 1" }).click();
  await page.getByRole("button", { name: "Restore this version" }).click();
  await expect(page.getByRole("textbox", { name: "Action", exact: true })).toHaveValue(/Basically I really checked/);
  await expect(page.getByText(/STORY BANK · VERSION 6/)).toBeVisible();

  // Another account sees nothing.
  const other = await browser.newContext();
  const stranger = await other.newPage();
  stranger.on("dialog", (d) => void d.accept());
  await signUpNurse(stranger);
  await stranger.goto(storyUrl);
  await expect(stranger.getByText(/Story not found|couldn't be found|not found/i).first()).toBeVisible();
  await stranger.goto("/stories");
  await expect(stranger.getByText("No stories yet")).toBeVisible();
  await other.close();

  // Deleting the story keeps the practice answer.
  await page.getByRole("button", { name: "Delete…" }).click();
  await expect(page).toHaveURL(/\/stories$/);
  await page.goto("/history");
  await expect(page.getByText(/Patient assessment under pressure/).first()).toBeVisible();
});

test("the story editor works at 320px in the light theme", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "light" })));
  await signUpNurse(page);
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto("/stories/new");
  await page.getByLabel("Title").fill("A missed handover");
  await page.getByLabel("Situation").fill("I forgot to hand over a pending blood result.");
  await page.getByRole("button", { name: "Save story" }).click();
  await expect(page).toHaveURL(/\/stories\/[0-9a-f-]+$/);
  await page.getByRole("button", { name: "Check for missing parts" }).click();
  await expect(page.getByText(/Task: what were you responsible for/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, "story editor at 320px, light");
});
