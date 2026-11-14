import AxeBuilder from "@axe-core/playwright";

import { chooseJob, expect, setTheme, test } from "./fixtures";

/**
 * Disputed feedback (Volume 12, prompt 7; docs/DISPUTES.md), against the real API: a nurse's weak
 * answer gets a retry that names two missed points; disputing one labels that retry (nothing
 * removed), the next version names only the undisputed point and says in one line what it didn't
 * suggest, a second device sees the same, the score never changes, and the point counts again only
 * when the learner presses the button. Synthetic data.
 */
const WEAK =
  "Patient assessment is something every nurse does on the ward. It is part of the job and it is " +
  "important to do it well because patients depend on nurses. I do it on my shifts like everyone else " +
  "on the team and I think it is a key skill to have in this job.";
const EXAMPLE = "Backs it up with a concrete example";
const STEPS = "Lays out clear steps or habits";
const QUESTION = "/careers/registered-nurse/questions/e-good-0";
const RETRY = "Retry: What good patient assessment looks like";

async function scan(page: import("@playwright/test").Page, what: string) {
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const result = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(result.violations.map((v) => v.id), `${what}, ${theme}`).toEqual([]);
  }
}

test("a disputed point stops shaping the plan, what came from it is labelled, and it counts again only when asked", async ({ page, browser }) => {
  const email = `dispute-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto(QUESTION);
  await page.getByRole("textbox", { name: "Your answer" }).fill(WEAK);
  await page.getByRole("button", { name: "Get feedback" }).click();
  const feedback = page.getByRole("region", { name: "Feedback", exact: true });
  const score = feedback.getByLabel(/^Score \d+ out of 100/);
  await expect(score).toBeVisible();
  const scoreLabel = await score.getAttribute("aria-label");

  // The plan before: the retry names both missed points.
  await page.goto("/plan");
  const retry = page.getByRole("article", { name: RETRY }).first();
  await expect(retry).toContainText(`it missed ${EXAMPLE.toLowerCase()}, ${STEPS.toLowerCase()}.`);
  await expect(retry).not.toContainText("disputed");

  // Dispute one point, with a private note.
  await page.goto(QUESTION);
  await page.getByRole("button", { name: /^Try 1/ }).click();
  await page.getByText("Your reflection, flags and checking again").click();
  await page.getByRole("button", { name: `Flag “${EXAMPLE}”` }).click();
  await page.getByRole("radio", { name: "I disagree" }).check();
  await page.getByLabel("Private note (optional)").fill("I described my own shifts");
  await page.getByRole("button", { name: "Save flag" }).click();
  const standing = page.getByText(/this point doesn't shape your plan until you count it again/);
  await expect(standing).toBeVisible();
  const day = (await standing.textContent())!.match(/^Disputed on (\d{1,2} [A-Z][a-z]+):/)![1];
  const answerUrl = page.url();
  await scan(page, "a standing dispute");

  // The same plan version: the retry stays, labelled, with the dispute one click away.
  await page.goto("/plan");
  await expect(retry).toContainText(`Based on feedback you disputed on ${day}:`); // the same day as the flag says
  await expect(retry).toContainText(`“${EXAMPLE}”`);
  await expect(page.getByRole("article").filter({ hasText: "Based on feedback you disputed" })).toHaveCount(await page.getByRole("article", { name: RETRY }).count());
  await scan(page, "the labelled plan");

  // A second device sees the same.
  const other = await browser.newContext();
  const second = await other.newPage();
  await second.goto("/login");
  await second.getByLabel("Email").fill(email);
  await second.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await second.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(second).toHaveURL(/\/dashboard$/);
  await second.goto("/plan");
  await expect(second.getByRole("article", { name: RETRY }).first()).toContainText(`“${EXAMPLE}”`);
  await other.close();

  // The plan's next version: the retry names only the undisputed point, and one line says why.
  const nextVersion = async () => {
    await page.goto("/plan/goals");
    await page.getByRole("button", { name: "Save goals" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await page.goto("/plan");
  };
  await nextVersion();
  await expect(retry).toContainText(`it missed ${STEPS.toLowerCase()}.`);
  await expect(retry).not.toContainText(EXAMPLE.toLowerCase());
  const withheld = page.getByRole("region", { name: "Not suggested (1)" });
  await expect(withheld).toContainText("not because there's nothing to practise");
  await expect(withheld).toContainText(`Not suggested: adding “${EXAMPLE}” to “What good patient assessment looks like”: you disputed this point on `);
  await scan(page, "what wasn't suggested");

  // The dispute's link opens the answer; its score is what it was.
  await withheld.getByRole("link", { name: "See the dispute" }).click();
  await expect(page).toHaveURL(/\/questions\/e-good-0\?answer=/);
  await expect(page.getByRole("region", { name: /^Feedback on try 1/ }).getByLabel(/^Score \d+ out of 100/)).toHaveAttribute("aria-label", scoreLabel!);

  // Counting it again is the learner's button; the flag and its note stay.
  await page.goto(answerUrl);
  await page.getByText("Your reflection, flags and checking again").click();
  await page.getByRole("button", { name: "Count it in my plan again" }).click();
  await expect(page.getByText(/Counted in your plan again since /)).toBeVisible();
  await expect(page.getByText("You disagreed")).toBeVisible();
  await expect(page.getByText("“I described my own shifts”")).toBeVisible();
  await page.goto("/plan");
  await expect(withheld).toContainText("You've counted it again since: it can come back when your plan next updates.");
  await nextVersion();
  await expect(retry).toContainText(`it missed ${EXAMPLE.toLowerCase()}, ${STEPS.toLowerCase()}.`);
  await expect(page.getByRole("region", { name: /Not suggested/ })).toHaveCount(0);
});
