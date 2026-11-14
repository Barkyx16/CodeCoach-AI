import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "./fixtures";

// Automated WCAG 2.1 A/AA checks (axe-core) on every main screen, on desktop and on a phone.
// They catch a useful class of problems (contrast, names, labels, landmarks, ARIA misuse) but
// not everything: keyboard flows are covered by the other journeys, and none of this replaces
// testing with a screen reader.
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function expectNoViolations(page: Page, view: string) {
  // Wait for any loading state to finish so dynamic content is what gets scanned.
  await expect(page.locator(".spinner")).toHaveCount(0, { timeout: 15_000 });
  const results = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  const summary = results.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
  }));
  expect(summary, `axe violations on ${view}`).toEqual([]);
}

test("public pages have no WCAG 2.1 A/AA violations", async ({ page }) => {
  for (const [path, heading] of [
    ["/", /practice/i],
    ["/login", /sign in|welcome/i],
    ["/register", /create|account/i],
    ["/forgot-password", /reset your password/i],
    ["/reset-password", /choose a new password/i],
    ["/verify-email", /confirm your email/i],
    ["/problems", /problems|library|practice/i],
    ["/problems?career=registered-nurse", /registered nurse interview questions/i],
    ["/careers/registered-nurse/questions/m-walk-0", /handle it/i],
    ["/learn?career=registered-nurse", /registered nurse lessons/i],
    ["/learn/se-sliding-window", /sliding windows/i],
    ["/scenarios?career=registered-nurse", /registered nurse scenarios/i],
    ["/scenarios/rn-two-patients", /two call lights/i],
    ["/help", /how codecoach works/i],
    ["/no-such-page", /page not found/i],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toContainText(heading);
    await expectNoViolations(page, path);
  }
});

test("signed-in screens have no WCAG 2.1 A/AA violations", async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  // The guest demo starts on the optional welcome, then opens the real starter problem.
  await expect(page).toHaveURL(/\/welcome$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Welcome");
  await expectNoViolations(page, "welcome");
  await page.getByRole("button", { name: "Start this problem" }).click();
  await expect(page).toHaveURL(/two-sum/);
  await expect(page.getByRole("heading", { name: "Two Sum", level: 1 })).toBeVisible();
  await expectNoViolations(page, "workspace");

  // Workspace with coach output on screen (desktop shows the coach panel side by side).
  if (test.info().project.name === "desktop") {
    await page.getByRole("button", { name: "Get a hint" }).click();
    await expect(page.getByText(/level 1/i).first()).toBeVisible();
    await page.getByRole("tab", { name: "Code review" }).click();
    await page.getByRole("button", { name: /review my code/i }).click();
    // What the coach will read comes first (docs/COACH_CONTEXT.md); nothing is sent until asked.
    await expect(page.getByRole("heading", { name: "What the coach will read" })).toBeVisible();
    await expectNoViolations(page, "workspace with the review's preview");
    await page.getByRole("button", { name: "Send for review" }).click();
    await expect(page.getByText(/AI feedback can be wrong/)).toBeVisible();
    await expectNoViolations(page, "workspace with hint and review");
  }

  // A written answer with its feedback on screen (the coach's result, quotes and advice).
  await page.goto("/careers/registered-nurse/questions/m-walk-0");
  await page.getByRole("textbox", { name: "Your answer" }).fill(
    "Last winter on a busy ward I was responsible for six patients. I checked the observations, called the doctor " +
      "about the sickest patient and asked a colleague to cover my bay. All six had their medicines on time.",
  );
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: "Feedback" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Feedback" })).toBeFocused();
  await expectNoViolations(page, "written answer with feedback");

  for (const path of ["/dashboard", "/analytics", "/analytics?career=registered-nurse", "/history", "/history?career=coding&type=coaching", "/interviews", "/interviews/questions", "/plan", "/plan/goals", "/settings", "/saved", "/notes", "/notes/new"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await expectNoViolations(page, path);
  }

  // A collection with an item, and the filtered question explorer.
  await page.goto("/saved");
  await page.getByLabel("New collection").fill("Accessibility check");
  await page.getByRole("button", { name: "Create collection" }).click();
  await expect(page.getByRole("heading", { name: "Accessibility check" })).toBeVisible();
  await expectNoViolations(page, "empty collection");
  await page.goto("/problems?view=questions&kind=behavioral&q=time");
  await expect(page.getByRole("button", { name: /Remove Format/ })).toBeVisible();
  await expectNoViolations(page, "filtered explorer");

  // A live question round (voice controls, engagement indicator) and its results page.
  await page.goto("/interviews/questions");
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page.getByText(/QUESTION 1 OF 5/)).toBeVisible();
  await expectNoViolations(page, "live question round");
  await page.getByRole("button", { name: "End early" }).click();
  await expect(page.getByText(/ENDED EARLY/)).toBeVisible();
  await expectNoViolations(page, "question round results");
});

test("the skip link is the first Tab stop and jumps to the main content", async ({ page }) => {
  for (const path of ["/", "/problems", "/problems/two-sum"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Skip to content" });
    await expect(skip).toBeFocused();
    await expect(skip).toBeInViewport(); // visible once focused, so sighted keyboard users see it
    await page.keyboard.press("Enter");
    await expect(page.locator("main#main")).toBeFocused();
  }
});
