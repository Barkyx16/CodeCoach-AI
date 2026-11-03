import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const VAGUE = "We handled it together as a team and everything was fine in the end, everyone did well.";

async function signUp(page: Page, career: string, tag: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`${tag}-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption(career);
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("a simulated panel: named speakers, a follow-up from the asking role, reload resume, perspectives in the review", async ({ page }) => {
  await signUp(page, "registered-nurse", "panel");
  await page.goto("/interviews/questions");
  await page.getByRole("group", { name: "Difficulty" }).getByText("Medium").click();
  await page.getByRole("radio", { name: /Panel interview/ }).check();
  await expect(page.getByRole("region", { name: /What to expect: Panel interview/ })).toContainText("Nurse manager asks");
  await page.getByRole("button", { name: "Start interview" }).click();

  await expect(page.getByText("NURSE MANAGER ASKS", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Panel" }).getByText("Nurse manager · speaking")).toBeVisible();
  await page.getByLabel("Your answer", { exact: true }).fill(VAGUE);
  await page.getByRole("button", { name: "Next question" }).click();
  // A vague answer gets one follow-up, from the same role, about what was missing.
  const followup = page.getByRole("heading", { level: 1, name: /Nurse manager asks:/ });
  await expect(followup).toBeVisible();
  await expect(followup).toBeFocused();
  // The follow-up survives a reload: the server holds the turn.
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: /Nurse manager asks:/ })).toBeVisible();
  await page.getByLabel("Your reply").fill("I checked his vital signs myself and I called the doctor straight away.");
  await page.getByRole("button", { name: "Send reply" }).click();
  await expect(page.getByText("CHARGE NURSE (PEER) ASKS", { exact: true })).toBeVisible();
  const scan = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(scan.violations.map((v) => v.id), "live panel").toEqual([]);

  // Finish: answer the rest; skip any follow-up (they're bounded at two per round).
  const answerBox = page.getByLabel("Your answer", { exact: true });
  const replyBox = page.getByLabel("Your reply");
  const results = page.getByRole("region", { name: "Panel perspectives (simulated)" });
  const position = page.locator(".round__bar .eyebrow");
  for (let i = 0; i < 10; i++) {
    await expect(answerBox.or(replyBox).or(results)).toBeVisible({ timeout: 15_000 });
    if (await results.isVisible()) break;
    if (await replyBox.isVisible()) {
      await page.getByRole("button", { name: "Skip follow-up" }).click();
      await expect(replyBox).toBeHidden();
      continue;
    }
    const before = await position.innerText();
    await answerBox.fill("I would assess first because it is urgent, then I told the charge nurse, and as a result he was stable in 20 minutes. I learned to escalate earlier.");
    await page.getByRole("button", { name: /Next question|Finish interview/ }).click();
    // Something changes: the next question, a follow-up, or the results.
    await expect.poll(async () =>
      (await results.isVisible()) || (await replyBox.isVisible()) || ((await position.isVisible()) && (await position.innerText()) !== before),
    { timeout: 15_000 }).toBe(true);
  }
  const persp = page.getByRole("region", { name: "Panel perspectives (simulated)" });
  await expect(persp).toBeVisible({ timeout: 15_000 });
  await expect(persp).toContainText("Not separate human judgments");
  await expect(page.getByText(/Asked by the nurse manager \(simulated role\)/).first()).toBeVisible();
});

test("a career without a reviewed panel shows why, and a behavioral round still works", async ({ page }) => {
  await signUp(page, "electrician", "elec");
  await page.goto("/interviews/questions");
  await expect(page.getByRole("radio", { name: /Panel interview/ })).toBeDisabled();
  await expect(page.getByText(/no reviewed panel for Electrician yet/)).toBeVisible();
  await page.getByRole("radio", { name: /Behavioral interview/ }).check();
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page.getByText(/ELECTRICIAN BEHAVIORAL INTERVIEW · QUESTION 1 OF 5/)).toBeVisible();
  await page.getByLabel("Your answer", { exact: true }).fill(VAGUE);
  await page.getByRole("button", { name: "Next question" }).click();
  await expect(page.getByRole("heading", { level: 1, name: /Interviewer asks: What did you personally do there/ })).toBeVisible();
  await page.getByRole("button", { name: "Skip follow-up" }).click();
  await expect(page.getByText(/QUESTION 2 OF 5/)).toBeVisible();
});
