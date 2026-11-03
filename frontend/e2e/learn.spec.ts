import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures";

const ANSWER =
  "Situation: an oxygen alarm went off while another patient needed help to the bathroom. I asked a nursing " +
  "assistant to help the first patient safely and went to the alarm, checked the probe and the patient's breathing, " +
  "and called the rapid response team with SBAR. As a result she was stable within 20 minutes, and I documented it.";

test("a nurse learns before practising: prerequisite, guided help, solution, check, resume, practice", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`learn-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click(); // the optional welcome

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Learn" }).click();
  await expect(page.getByRole("heading", { name: "Registered Nurse lessons" })).toBeVisible();
  await page.getByRole("link", { name: "Prioritizing when several patients need you" }).click();
  await expect(page.getByRole("note")).toContainText("not clinical guidance");

  // Open the prerequisite and come back.
  await page.getByRole("region", { name: "Before you start" }).getByRole("link", { name: "SBAR for handoffs and escalation" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "SBAR for handoffs and escalation" })).toBeVisible();
  await page.getByRole("link", { name: "Back to Prioritizing when several patients need you" }).click();
  await expect(page.getByRole("region", { name: "Before you start" })).toContainText("Started");

  // Guided help one step at a time; the solution only after a spoiler warning; the draft is untouched.
  const exercise = page.getByRole("region", { name: "Try it" });
  await exercise.getByLabel("Your answer").fill("I'd go to the alarm first because");
  await exercise.getByRole("button", { name: /Show step 1 of 4/ }).click();
  await expect(exercise.getByText("Which situation could become life-threatening in minutes?")).toBeVisible();
  await exercise.getByLabel(/On my own/).check();
  await exercise.getByRole("button", { name: "Show solution…" }).click();
  await exercise.getByRole("alertdialog").getByRole("button", { name: "Show the solution" }).click();
  await expect(exercise.getByText(/The oxygen alarm comes first/)).toBeVisible();
  await expect(exercise.getByLabel("Your answer")).toHaveValue("I'd go to the alarm first because");

  // Read, then the check: a wrong attempt, then a pass.
  await page.getByRole("button", { name: "I've read this unit" }).click();
  await expect(page.getByText(/Marked as read for version 1/)).toBeVisible();
  const check = page.getByRole("region", { name: "Check yourself" });
  await check.getByLabel("A patient asking about discharge").check();
  await check.getByLabel("Saying how you'd get help and escalate").check();
  await check.getByLabel("A patient who is bleeding now").check();
  await check.getByRole("button", { name: "Check my answers" }).click();
  await expect(check.getByText(/2 of 3 right/)).toBeVisible();
  await check.getByLabel("A patient with noisy, labored breathing").check();
  await check.getByRole("button", { name: "Check again" }).click();
  await expect(check.getByText(/Passed: 3 of 3 right/)).toBeVisible();
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => v.id), "unit page").toEqual([]);

  // Reload: progress and the draft are still there.
  await page.reload();
  await expect(page.getByRole("region", { name: "Next step" })).toContainText("Answer “Handle it: a patient's vital signs drop suddenly”");
  await expect(page.getByRole("region", { name: "Try it" }).getByLabel("Your answer")).toHaveValue("I'd go to the alarm first because");
  await expect(page.getByRole("region", { name: "Your progress on this unit" })).toContainText("Check passed: every answer right");

  // Practise for real; only then is "practised" recorded.
  await page.getByRole("region", { name: "Practice" }).getByRole("link", { name: /Answer “Handle it/ }).click();
  await page.getByLabel("Your answer", { exact: true }).fill(ANSWER);
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: "Feedback" })).toBeVisible();
  await page.getByRole("link", { name: "Back to Prioritizing when several patients need you" }).click();
  await expect(page.getByRole("region", { name: "Practice" })).toContainText(/Practised since you started this unit: answered, scored \d+\/100/);
});

test("a coding unit shows accessible code and passing its check doesn't solve a problem", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await page.getByRole("button", { name: "Start this problem" }).click(); // the optional welcome
  await expect(page).toHaveURL(/two-sum/);
  await expect(page.getByRole("region", { name: "Learn first" }).getByRole("link", { name: "Hash maps for fast lookup" })).toBeVisible();
  await page.getByRole("region", { name: "Learn first" }).getByRole("link", { name: "Hash maps for fast lookup" }).click();
  const code = page.getByRole("region", { name: "Java code: Two Sum in one pass" });
  await expect(code).toContainText("Map<Integer, Integer> indexOf");
  await code.focus();
  await expect(code).toBeFocused();
  const check = page.getByRole("region", { name: "Check yourself" });
  await check.getByLabel("It stops an element from being paired with itself.").check();
  await check.getByLabel("O(n) on average").check();
  await check.getByLabel("HashSet<Integer>").check();
  await check.getByRole("button", { name: "Check my answers" }).click();
  await expect(check.getByText(/Passed: 3 of 3 right/)).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/learn-unit.png", fullPage: false });
  // A 320px-wide screen: the outline stacks above the content and nothing scrolls sideways.
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/learn/se-hash-map-lookup");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  // A lesson is public, so it shows before the session is restored: wait for the signed-in header
  // before checking the layout. (A refresh cut off by the next page load is recovered on that
  // load; e2e/refresh-recovery.spec.ts covers it.)
  await expect(page.getByRole("link", { name: /account settings$/, includeHidden: true })).toBeAttached(); // in the closed menu at 320px
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  await page.screenshot({ path: "e2e/screenshots/learn-unit-320.png", fullPage: false });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: "Summary" })).toContainText(/0\s*Solved|Solved\s*0/);
});
