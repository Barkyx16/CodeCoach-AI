import AxeBuilder from "@axe-core/playwright";
import { chooseJob, expect, test } from "./fixtures";

const WEAK = "We handled it together as a team and it was fine in the end.";
const STRONG =
  "Last winter I was the night nurse for five patients when one man's oxygen dropped during my 2 a.m. assessment. " +
  "I rechecked his vital signs, started oxygen per protocol, and called the rapid response team myself. I asked the " +
  "charge nurse to cover my other patients and updated the doctor. He was stable within 30 minutes, and I learned " +
  "to escalate early instead of waiting to be sure.";

test("review a round, retry one question, compare, queue it, and come back to History", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`review-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click(); // the optional welcome

  await page.goto("/interviews/questions");
  await page.getByRole("button", { name: "Start interview" }).click();
  for (const [n, answer] of [WEAK, WEAK].entries()) {
    await expect(page.getByText(new RegExp(`QUESTION ${n + 1} OF 5`))).toBeVisible();
    await page.getByLabel("Your answer", { exact: true }).fill(answer);
    await page.getByRole("button", { name: "Next question" }).click();
  }
  await expect(page.getByText(/QUESTION 3 OF 5/)).toBeVisible();
  page.on("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: "End early" }).click();

  // The review states it ended early and grounds its advice in the answers.
  await expect(page.getByText(/MOCK INTERVIEW · ENDED EARLY/)).toBeVisible();
  await expect(page.getByText(/Ended early: 2 of 5 questions answered/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Work on next" })).toBeVisible();
  const evidence = page.locator(".review__improvements .evidence-link").first();
  await evidence.click();
  await expect(page).toHaveURL(/item=q\d/);
  await expect(page.locator("#review-detail")).toContainText(WEAK);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => v.id), "review page").toEqual([]);

  // Retry the second question; the original stays and the two are compared.
  await page.locator(".review__timeline .timeline-item").nth(1).click();
  await page.locator("#review-detail").getByRole("button", { name: "Save for later review" }).click();
  await expect(page.locator("#review-detail").getByText("In your review queue")).toBeVisible();
  await page.locator("#review-detail").getByRole("link", { name: "Retry this question" }).click();
  await expect(page.getByText(/Your original answer \(\d+\/100\)/)).toBeVisible();
  await page.getByLabel("Your new answer").fill(STRONG);
  await page.getByRole("button", { name: "Get feedback and compare" }).click();
  const comparison = page.getByRole("region", { name: "How your latest attempt compares" });
  await expect(comparison).toContainText(WEAK);
  await expect(comparison).toContainText(/Latest retry · \d+\/100 \(\+\d+\)/);
  await expect(comparison.getByRole("heading", { name: "Improved" })).toBeVisible();
  await page.getByRole("link", { name: "Back to the review" }).click();
  await expect(page.locator("#review-detail")).toContainText(WEAK); // original answer untouched
  await expect(page.getByRole("link", { name: "Compare 1 retry" })).toBeVisible();

  // The retry counted as answering the saved question again, so the queue rescheduled it and says why.
  await page.goto("/reviews");
  await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible();
  await expect(page.getByText(/Last answered .* scoring \d+\/100/)).toBeVisible();

  // From filtered History, open the interview and return to the same place.
  await page.goto("/history?type=interview");
  await page.getByRole("link", { name: /Registered Nurse question round/ }).click();
  await expect(page.getByText(/MOCK INTERVIEW · ENDED EARLY/)).toBeVisible();
  await page.getByRole("link", { name: "Back to History" }).click();
  await expect(page).toHaveURL(/\/history\?type=interview$/);
});
