import { chooseJob, expect, test, type Browser, type Page } from "./fixtures";

/**
 * One interview, two devices (separate browser contexts: separate storage and sessions) for the
 * same synthetic account, and a stranger. The server decides; each device is told what happened
 * and keeps its own unsent text:
 * - device B's start page names A's round in progress (what, how far, time left) and offers to
 *   resume it instead of a Start that can only fail;
 * - B resumes at the same question with the same server clock (resuming doesn't reset it);
 * - A answers; B, still showing the old question, sends its own answer: refused, the round shows
 *   the next question, and B's text stays on screen (and in B's storage) until B dismisses it;
 * - a reload mid-round lands on the current question, and the answer is recorded once;
 * - the stranger can't open the interview, and the stranger's own Start isn't blocked by it.
 */
const PASSWORD = "CorrectHorse42";
const ANSWER_A =
  "I would check the patient's vital signs and airway first, then call the charge nurse and the doctor, and " +
  "document what I saw, because patient safety comes first and the whole team needs the same picture.";

async function signUp(page: Page, email: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function signIn(browser: Browser, email: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
  return page;
}

const clockSeconds = async (page: Page) => {
  const label = (await page.getByRole("timer").getAttribute("aria-label")) ?? "";
  const [m, s] = label.split(" ")[0]!.split(":").map(Number);
  return m! * 60 + s!;
};

test("one round on two devices: resume with context, a stale answer kept, a reload, and a stranger shut out", async ({ page: a, browser }) => {
  test.setTimeout(120_000);
  const email = `continuity-${Date.now()}@example.com`;
  await signUp(a, email);
  await a.goto("/interviews/questions");
  await a.getByRole("button", { name: "Start interview" }).click();
  await expect(a.getByText(/QUESTION 1 OF/)).toBeVisible();
  const url = a.url();
  const firstTitle = await a.getByRole("heading", { level: 1 }).innerText();

  // Device B: the start page names the round in progress instead of offering a Start that fails.
  const b = await signIn(browser, email);
  await b.goto("/interviews/questions");
  const card = b.getByRole("status").filter({ hasText: "You already have an interview in progress" });
  await expect(card).toContainText("Registered Nurse interview");
  await expect(card).toContainText(/0 of \d questions done/);
  await expect(card).toContainText(/\d+:\d\d left/);
  await expect(b.getByRole("button", { name: "Start interview" })).toBeDisabled();
  await card.getByRole("link", { name: "Resume it" }).click();
  await expect(b).toHaveURL(url);
  await expect(b.getByRole("heading", { level: 1 })).toHaveText(firstTitle); // the same question
  const [left, leftB] = [await clockSeconds(a), await clockSeconds(b)];
  expect(Math.abs(left - leftB)).toBeLessThanOrEqual(3); // one server clock, not restarted on resume

  // A answers. B still shows question 1 and sends its own answer to it.
  await a.getByLabel("Your answer", { exact: true }).fill(ANSWER_A);
  await a.getByRole("button", { name: "Next question" }).click();
  await expect(a.getByText(/QUESTION 2 OF/)).toBeVisible();
  await b.getByLabel("Your answer", { exact: true }).fill("My answer typed on the other device.");
  await b.getByRole("button", { name: "Next question" }).click();
  const kept = b.getByRole("region", { name: "Your unsent answer to question 1" });
  await expect(kept).toContainText("already has an answer");
  await expect(kept).toContainText("My answer typed on the other device.");
  await expect(b.getByText(/QUESTION 2 OF/)).toBeVisible(); // B now shows where the round is
  await kept.getByRole("button", { name: "Dismiss" }).click();
  await expect(kept).toHaveCount(0);

  // A reload mid-round lands on the current question.
  await a.reload();
  await expect(a.getByText(/QUESTION 2 OF/)).toBeVisible();
  // End it on A: the results hold one answer to question 1, A's, never B's.
  a.once("dialog", (d) => void d.accept());
  await a.getByRole("button", { name: "End early" }).click();
  await expect(a.getByRole("heading", { name: /interview results/ })).toBeVisible();
  await expect(a.getByText(ANSWER_A.slice(0, 60)).first()).toBeVisible();
  await expect(a.getByText("My answer typed on the other device.")).toHaveCount(0);
  // B finds out the round ended when it looks again: results, not a dead form.
  await b.reload();
  await expect(b.getByRole("heading", { name: /interview results/ })).toBeVisible();

  // A stranger can't open it, and the stranger's own Start isn't blocked by it.
  const stranger = await (await browser.newContext()).newPage();
  await signUp(stranger, `stranger-${Date.now()}@example.com`);
  await stranger.goto(url.replace(/^https?:\/\/[^/]+/, ""));
  await expect(stranger.getByText(/Interview not found|couldn't find|isn't available/i).first()).toBeVisible();
  await stranger.goto("/interviews/questions");
  await expect(stranger.getByRole("button", { name: "Start interview" })).toBeEnabled();
});
