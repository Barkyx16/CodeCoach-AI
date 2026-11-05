import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { chooseJob, expect, test, type Page } from "./fixtures";

// Content quality end to end with the real API: reports pinned to a version, duplicates grouped,
// an admin (granted from the command line, the only way) triages, corrects and retires, and the
// learner sees honest outcomes. Everyone involved is a local test account.

// A question no other spec uses: this journey corrects it and briefly retires it.
const QUESTION = "/careers/registered-nurse/questions/m-walk-1";
const ANSWER = "Last month a daughter was angry that her father waited for pain relief. I listened, apologised, explained the delay, called the doctor and checked back within 30 minutes; she thanked the team.";

async function signUpNurse(page: Page, tag: string): Promise<string> {
  const email = `${tag}-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click(); // the optional welcome
  await expect(page).toHaveURL(/\/dashboard$/);
  return email;
}

function grantAdmin(email: string) {
  // The same command an operator runs; there is no API for it.
  execFileSync(process.env.PYTHON ?? "python", ["-m", "app.cli", "grant-admin", email], {
    cwd: resolve(process.cwd(), "../backend"),
    env: { ...process.env, DATABASE_URL: "sqlite:///./e2e.db", SECRET_KEY: "e2e-secret-key-that-is-at-least-32-characters" },
  });
}

async function report(page: Page, category: string, details: string) {
  await page.getByRole("button", { name: "Report an issue" }).click();
  await page.getByRole("radio", { name: category }).check();
  await page.getByLabel(/Details/).fill(details);
  await page.getByRole("button", { name: "Send report" }).click();
  await expect(page.getByText(/Thanks, it's been reported/)).toBeVisible();
}

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })), where).toEqual([]);
}

test("report, triage, correct and retire: every party sees exactly what they should", async ({ page, browser }) => {
  page.on("dialog", (d) => void d.accept());
  // A learner answers (version 1), saves the question and reports unclear wording.
  await signUpNurse(page, "learner");
  await page.goto(QUESTION);
  const originalPrompt = await page.locator(".question-page__prompt p").innerText();
  await page.getByRole("textbox", { name: "Your answer" }).fill(ANSWER);
  await page.getByRole("button", { name: "Get feedback" }).click();
  const feedback = page.getByRole("region", { name: "Feedback", exact: true });
  await expect(feedback).toBeVisible();
  const score = await feedback.locator(".score-pill strong").innerText();
  await page.getByRole("button", { name: "Bookmark" }).click();
  await page.locator(".content-info summary").click();
  await expect(page.getByText("Not reviewed by a subject-matter expert")).toBeVisible();
  await expect(page.getByText(/Generated from the Registered Nurse career profile/)).toBeVisible();
  await report(page, "Ambiguous or unclear wording", "<script>alert(1)</script> Which vital signs?");
  await axe(page, "question page with report sent");

  // A second learner reports the same thing: grouped as a likely duplicate, not merged away.
  const second = await browser.newContext();
  const other = await second.newPage();
  await signUpNurse(other, "second");
  await other.goto(QUESTION);
  await report(other, "Ambiguous or unclear wording", "Unclear what to describe.");
  await other.goto("/admin/reports"); // not an admin: looks like any missing page
  await expect(other.getByRole("heading", { level: 1, name: /page not found/i })).toBeVisible();
  await second.close();

  // An admin triages.
  const adminContext = await browser.newContext();
  const admin = await adminContext.newPage();
  admin.on("dialog", (d) => void d.accept());
  const adminEmail = await signUpNurse(admin, "admin");
  grantAdmin(adminEmail);
  await admin.reload();
  await admin.getByRole("link", { name: "Triage" }).click();
  await expect(admin.getByRole("heading", { level: 1, name: "Reports" })).toBeVisible();
  const group = admin.locator(".admin-groups > li").filter({ hasText: "m-walk-1" });
  // At least the two reports above (a reused local database may hold earlier runs' too).
  await expect.poll(() => group.locator(".admin-reports > li").count()).toBeGreaterThanOrEqual(2);
  await expect(group.getByText(/likely duplicate/).first()).toBeVisible();
  await axe(admin, "admin report list");
  await group.getByRole("link", { name: "Ambiguous or unclear wording" }).first().click();
  await expect(admin.getByText("<script>alert(1)</script> Which vital signs?")).toBeVisible(); // as text
  await admin.getByLabel("Status", { exact: true }).selectOption("investigating");
  await admin.getByLabel(/Internal note/).fill("Profile check needed.");
  await admin.getByRole("button", { name: "Save status" }).click();
  await expect(admin.getByText("Internal: Profile check needed.")).toBeVisible();
  const prompt = admin.getByLabel("Prompt");
  await prompt.fill("A family member is angry about a delay in their relative's care. What do you say first, who do you involve, and how do you follow up?");
  await admin.getByLabel(/What changed, in plain language/).fill("The question now says what to cover: what you say first, who you involve and how you follow up.");
  await admin.getByRole("button", { name: "Publish version 2" }).click();
  await expect(admin.getByText(/Version 2 · Active/)).toBeVisible();
  await axe(admin, "admin report detail");

  // The learner: the change is explained, the old answer and score are untouched, the report resolved.
  await page.goto(QUESTION);
  const changed = page.locator(".banner").filter({ hasText: "This question changed since you answered it" });
  await expect(changed).toContainText("version 1 → 2");
  await expect(changed).toContainText("what you say first, who you involve and how you follow up");
  await expect(page.locator(".question-page__prompt p")).toContainText("What do you say first");
  await page.locator(".past-answers__item").first().click();
  const old = page.locator(".answered-version");
  await old.locator("summary").click();
  await expect(old).toContainText(originalPrompt);
  await expect(page.getByRole("region", { name: /Feedback/ }).locator(".score-pill strong")).toHaveText(score);
  await page.goto("/reports");
  await expect(page.getByText("Resolved")).toBeVisible();
  await expect(page.getByText(/Corrected in version 2: The question now says what to cover/)).toBeVisible();
  await expect(page.getByText("Profile check needed.")).toHaveCount(0); // internal notes stay internal
  await axe(page, "my reports");

  // Retire it: no longer offered, still readable, and saved items say why.
  await admin.goto("/admin/reports?status=all");
  await admin.locator(".admin-groups > li").filter({ hasText: "m-walk-1" }).getByRole("link").last().click();
  await admin.getByLabel("Reason (learners see this)").fill("Under review after reports: not used for practice until fixed.");
  await admin.getByRole("button", { name: "Retire" }).click();
  await expect(admin.getByRole("button", { name: "Restore for practice" })).toBeVisible();

  await page.goto(QUESTION);
  await expect(page.getByText(/Under review after reports: not used for practice until fixed\./).first()).toBeVisible();
  await page.getByRole("textbox", { name: "Your answer" }).fill("Another go.");
  await expect(page.getByRole("button", { name: "Get feedback" })).toBeDisabled();
  await page.goto("/saved");
  const saved = page.locator(".saved-list__item").filter({ hasText: "Retired:" });
  await expect(saved).toContainText("You can still open it");
  await expect(saved.getByRole("link")).toHaveAttribute("href", QUESTION);
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto(QUESTION);
  await page.getByRole("button", { name: "Report an issue" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

  // Leave the shared test database as it was for other specs: restore the question.
  await admin.getByRole("button", { name: "Restore for practice" }).click();
  await expect(admin.getByRole("heading", { name: "Retire" })).toBeVisible();
  await adminContext.close();
});
