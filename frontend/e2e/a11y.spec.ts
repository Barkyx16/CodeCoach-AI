import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

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
    ["/problems", /problems|library|practice/i],
    ["/no-such-page", /page not found/i],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toContainText(heading);
    await expectNoViolations(page, path);
  }
});

test("signed-in screens have no WCAG 2.1 A/AA violations", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/two-sum/);
  await expect(page.getByRole("heading", { name: "Two Sum", level: 1 })).toBeVisible();
  await expectNoViolations(page, "workspace");

  // Workspace with coach output on screen (desktop shows the coach panel side by side).
  if (test.info().project.name === "desktop") {
    await page.getByRole("button", { name: "Get a hint" }).click();
    await expect(page.getByText(/level 1/i).first()).toBeVisible();
    await page.getByRole("tab", { name: "Code review" }).click();
    await page.getByRole("button", { name: /review my code/i }).click();
    await expect(page.getByText(/AI feedback can be wrong/)).toBeVisible();
    await expectNoViolations(page, "workspace with hint and review");
  }

  for (const path of ["/dashboard", "/analytics", "/history", "/interviews", "/settings"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await expectNoViolations(page, path);
  }
});
