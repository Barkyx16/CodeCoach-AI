import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "./fixtures";
import { roundPosition } from "./rounds";

const VAGUE = "We handled it together as a team and everything was fine in the end, everyone did well.";

async function signUp(page: Page, career: string, tag: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`${tag}-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption(career);
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click(); // the optional welcome
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
  for (let i = 0; i < 10; i++) {
    await expect(answerBox.or(replyBox).or(results)).toBeVisible({ timeout: 15_000 });
    if (await results.isVisible()) break;
    if (await replyBox.isVisible()) {
      await page.getByRole("button", { name: "Skip follow-up" }).click();
      await expect(replyBox).toBeHidden();
      continue;
    }
    const before = await roundPosition(page);
    await answerBox.fill("I would assess first because it is urgent, then I told the charge nurse, and as a result he was stable in 20 minutes. I learned to escalate earlier.");
    await page.getByRole("button", { name: /Next question|Finish interview/ }).click();
    // Something changes: the next question, a follow-up, or the results. Every check here returns
    // at once; none waits for an element the round may have just removed (see e2e/rounds.ts).
    await expect.poll(async () =>
      (await results.isVisible()) || (await replyBox.isVisible()) || ((await roundPosition(page)) ?? before) !== before,
    { timeout: 15_000 }).toBe(true);
  }
  const persp = page.getByRole("region", { name: "Panel perspectives (simulated)" });
  await expect(persp).toBeVisible({ timeout: 15_000 });
  await expect(persp).toContainText("Not separate human judgments");
  await expect(page.getByText(/Asked by the nurse manager \(simulated role\)/).first()).toBeVisible();
});

test("checking a round's progress just as it ends returns at once instead of waiting for a question that's gone", async ({ page }) => {
  // The panel journey's check used to read "is the question line there?" and then "what does it
  // say?". When the round ended between the two, the second read waited for a line that never
  // came back. Here the last step's answer is held so the round ends exactly between them.
  await signUp(page, "electrician", "round-end");
  await page.goto("/interviews/questions");
  await page.getByRole("radio", { name: /Behavioral interview/ }).check();
  await page.getByRole("button", { name: "Start interview" }).click();
  for (let n = 1; n < 5; n++) {
    await expect(page.getByText(new RegExp(`QUESTION ${n} OF 5`))).toBeVisible();
    await page.getByRole("button", { name: "Skip", exact: true }).click();
  }
  await expect(page.getByText(/QUESTION 5 OF 5/)).toBeVisible();
  let release!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/v1/interviews/*/skip", async (route) => { await held; await route.continue(); }, { times: 1 });
  await page.getByRole("button", { name: "Skip", exact: true }).click(); // the last step: ends the round

  expect(await roundPosition(page)).toMatch(/QUESTION 5 OF 5/); // first check: the question is there
  release(); // the round ends between the two checks
  await expect(page.getByRole("heading", { level: 1, name: /Electrician interview results/ })).toBeVisible();
  const started = Date.now();
  expect(await roundPosition(page)).toBeNull(); // second check: gone, and it says so at once
  expect(Date.now() - started).toBeLessThan(2_000);
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
