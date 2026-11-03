import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "./fixtures";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function signUp(page: Page, career: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`scen-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption(career);
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click(); // the optional welcome
  await expect(page).toHaveURL(/\/dashboard$/);
}

const cont = (page: Page) => page.getByRole("button", { name: "Continue" });
async function choose(page: Page, label: string | RegExp) {
  await page.getByLabel(label).check();
  await page.getByRole("button", { name: "Confirm this decision" }).click();
}

test("a nurse takes an imperfect path, resumes after reload, debriefs it, then tries another approach", async ({ page }) => {
  await signUp(page, "registered-nurse");
  await page.goto("/interviews");
  await page.getByRole("link", { name: "branching scenario" }).click();
  await page.getByRole("link", { name: "Two call lights at once" }).click();
  await expect(page.getByText("Medical-surgical nurse at the start of a day shift")).toBeVisible();
  await page.getByRole("button", { name: "Start the scenario" }).click();

  await cont(page).click();
  await cont(page).click();
  await choose(page, /Bed 7, because their medicine is due/);
  await expect(page.getByRole("list", { name: "What has happened so far" })).toContainText("Risky");
  // Reload mid-scenario: the server remembers where we are.
  await page.reload();
  await expect(page.getByRole("heading", { level: 2, name: "Meanwhile" })).toBeVisible();
  await cont(page).click();
  await cont(page).click();
  await choose(page, /Recheck him in 30 minutes/);
  await cont(page).click();
  await page.getByLabel("Your response").fill("I would escalate earlier using SBAR because his breathing and saturation were getting worse.");
  await page.getByRole("button", { name: "Send response" }).click();

  const debrief = page.getByRole("region", { name: "Debrief" });
  await expect(debrief).toContainText("Escalation delayed (simulated)");
  await expect(debrief).toContainText("Bed 7, because their medicine is due");
  await expect(debrief).toContainText("No AI commentary was generated");
  const scan = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  expect(scan.violations.map((v) => v.id), "debrief").toEqual([]);
  const original = page.url();

  // Another approach is a separate attempt that reaches the other ending.
  await debrief.getByRole("button", { name: "Try another approach" }).click();
  await expect(page.getByText("Exploration: a separate attempt; your original is kept")).toBeVisible();
  await cont(page).click();
  await cont(page).click();
  await choose(page, /Bed 3, and ask a colleague/);
  await cont(page).click();
  await choose(page, /Follow the unit protocol/);
  await page.getByLabel("Your response").fill(
    "Situation: bed 3 is short of breath and his saturation is dropping. Background: day 1 after hip surgery. " +
    "Assessment: I'm worried he's deteriorating. Recommendation: please come and see him now.",
  );
  await page.getByRole("button", { name: "Send response" }).click();
  await expect(page.getByRole("region", { name: "Debrief" })).toContainText("Escalated promptly (simulated)");

  // The original attempt is unchanged.
  await page.goto(original);
  await expect(page.getByRole("region", { name: "Debrief" })).toContainText("Escalation delayed (simulated)");
});

test("a software engineer's incident: the fast path, on a narrow screen", async ({ page }) => {
  await signUp(page, "software-engineer");
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/scenarios");
  await page.getByRole("link", { name: "Checkout errors after a deploy" }).click();
  await page.getByRole("button", { name: "Start the scenario" }).click();
  await cont(page).click();
  await choose(page, "Roll back the deploy, then investigate");
  await cont(page).click();
  await page.getByLabel("Your response").fill("Customers saw checkout errors from 14:05 for about 6 minutes. We rolled back and it's stable; we'll follow up with a postmortem.");
  await page.getByRole("button", { name: "Send response" }).click();
  await expect(page.getByRole("region", { name: "Debrief" })).toContainText("Contained in about 6 minutes (simulated)");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  await page.screenshot({ path: "e2e/screenshots/scenario-debrief-320.png", fullPage: false });
});
