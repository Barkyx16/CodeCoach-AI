import AxeBuilder from "@axe-core/playwright";

import { chooseJob, expect, setTheme, test } from "./fixtures";

/**
 * One comparison contract (Volume 12, prompt 6; docs/COMPARING_ATTEMPTS.md), against the real API:
 * a nurse answers a question, then answers it again too briefly, then a third time. The question
 * page and the progress chart's list say the same about each pair, word for word; the chart counts
 * only the answers whose scores compare and says how many. Synthetic data.
 */
const LONG = "Last winter I noticed a patient's oxygen dropping during my 2 a.m. patient assessment. I checked his vital " +
  "signs, started oxygen per protocol and called the rapid response team. I updated the doctor and documented " +
  "everything. He was stable within 30 minutes and I learned to escalate early.";
const SHORT = "I called for help and it went fine.";
const LONGER = `${LONG} Since then I teach new nurses to trust the early signs and to call for help sooner.`;

test("the question page and the progress chart say the same about the same answers", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`compare-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto("/careers/registered-nurse/questions/e-good-0");
  const box = page.getByRole("textbox", { name: "Your answer" });
  const recap = page.getByRole("region", { name: "What next" });
  for (const text of [LONG, SHORT, LONGER]) {
    await box.fill(text);
    await page.getByRole("button", { name: "Get feedback" }).click();
    await expect(page.getByRole("region", { name: "Feedback", exact: true })).toBeVisible();
    await page.goto("/careers/registered-nurse/questions/e-good-0");
  }

  // The question page: try 3 against try 2 (too short): what was written compares, the numbers don't.
  await page.getByRole("button", { name: /^Try 3/ }).click();
  const third = recap.locator(".answer-recap__comparison");
  await expect(third).toContainText("Compared with try 2. Partly comparable: one was too short to score");
  await expect(third).not.toContainText(/score \d+, now \d+/);
  const thirdExplanation = (await third.innerText()).replace(/^Compared with try 2\. /, "").split(" (Comparison rules v1)")[0];
  await page.getByRole("button", { name: /^Try 2/ }).click();
  await expect(recap.locator(".answer-recap__comparison")).toContainText("Compared with try 1. ");
  const secondExplanation = (await recap.locator(".answer-recap__comparison").innerText()).replace(/^Compared with try 1\. /, "").split(" (Comparison rules v1)")[0];

  // The progress chart: two of the three are counted, and the list says the same, word for word.
  await page.goto("/analytics?range=30");
  await expect(page.getByText(/Graded by fixed rules, rubric v\d+, scored 0-100: 2 answers counted\./)).toBeVisible();
  await expect(page.getByText(/Not in the trend: 1 answer \(too short to score\)\./)).toBeVisible();
  await page.getByText("Answers in this range, and which the trend counts").click();
  await expect(page.getByText("2 of 3 answers are in the trend.", { exact: false })).toBeVisible();
  const rows = page.locator(".chart-answers__list > li");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText(`Compared with your answer before it: ${thirdExplanation}`);
  await expect(rows.nth(1)).toContainText(`Compared with your answer before it: ${secondExplanation}`);
  await expect(rows.nth(1)).toContainText("Not in the trend: too short to score");
  await expect(rows.nth(2)).toContainText("Your first answer to this question.");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(scan.violations.map((v) => v.id), `analytics, ${theme}`).toEqual([]);
  }

  // Every answer is reachable from the chart: the too-short one opens on its own page.
  await rows.nth(1).getByRole("link").click();
  await expect(page).toHaveURL(/\/questions\/e-good-0\?answer=/);
  await expect(page.getByRole("region", { name: /^Feedback on try 2/ })).toBeVisible();
});
