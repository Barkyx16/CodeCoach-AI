import AxeBuilder from "@axe-core/playwright";

import { chooseJob, expect, setTheme, test } from "./fixtures";

/**
 * Reviewed follow-up questions (Volume 12, prompt 4; docs/FOLLOW_UPS.md), against the real API:
 * after two scored answers to "keeping patients informed", the page offers the reviewed related
 * question about families with what's the same and what's different, worded carefully; answering it
 * from the offer links the two, and the first question's page lists it beside the original with its
 * own score, never merged. Synthetic data.
 */
const FIRST = "Every morning I tell each patient the plan for the day: tests, medicines and when the doctor will come. " +
  "When something changes I go back and explain it in plain words, check they understood by asking them to tell me " +
  "the plan, and write it on the whiteboard in the room. Patients asked fewer worried questions and complaints dropped.";
const SECOND = FIRST + " I also note what each patient asked so the next shift can keep them informed the same way.";
const FAMILY = "Each afternoon I call the family of every patient I look after with the plan and what changed today. " +
  "I use plain words, ask what they understood, and tell them when I will call again. When a son was worried about " +
  "a new medicine, I explained why it was started and arranged for the doctor to talk to him; he thanked the team.";

test("a reviewed related question is offered after practice, answered as its own attempt, and listed beside the original", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`followup-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  const url = "/careers/registered-nurse/questions/e-inform-0";
  await page.goto(url);
  const box = page.getByRole("textbox", { name: "Your answer" });
  const heading = page.getByRole("heading", { name: "A related question" });

  // One answer: not offered yet (the threshold is two answers long enough to score).
  await box.fill(FIRST);
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: "Feedback", exact: true })).toBeVisible();
  await expect(heading).toHaveCount(0);

  // A second: the reviewed relationship is offered, with what's shared and what's different.
  await page.getByRole("region", { name: "What next" }).getByRole("button", { name: "Revise this answer" }).click();
  await box.fill(SECOND);
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("button", { name: /^Try 2/ })).toBeVisible();
  await page.reload();
  await expect(heading).toBeVisible();
  const card = page.locator("section").filter({ has: heading });
  await expect(card).toContainText("patients' families instead of patients");
  await expect(card).toContainText("Not previously attempted in this app.");
  await expect(card).not.toContainText(/new to you|never seen|mastered/i);
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(scan.violations.map((v) => v.id), `offer, ${theme}`).toEqual([]);
  }

  // Answered from the offer: its own attempt, linked to the answer it follows.
  await card.getByRole("link").first().click();
  await expect(page).toHaveURL(/\/questions\/e-inform-2\?followUpOf=/);
  await expect(page.getByText(/A follow-up to your answer to a related question\. That answer stays as it is/)).toBeVisible();
  const sent = page.waitForResponse((r) => r.url().includes("/questions/e-inform-2/answers") && r.request().method() === "POST");
  await box.fill(FAMILY);
  await page.getByRole("button", { name: "Get feedback" }).click();
  const reply = await sent;
  expect(reply.status()).toBe(201);
  expect(reply.request().postDataJSON()?.follows_up_answer_id).toBeTruthy();
  await expect(page.getByRole("region", { name: "Feedback", exact: true })).toBeVisible();

  // Back on the first question: listed beside its answers with its own score; nothing combined.
  await page.goto(url);
  const answered = page.getByRole("heading", { name: "Follow-ups you answered" });
  await expect(answered).toBeVisible();
  const list = answered.locator("xpath=..");
  await expect(list).toContainText(/\d+\/100/);
  await expect(list).toContainText(/Scores aren't combined/);
  await expect(list).not.toContainText(/average/i);
  await expect(page.getByRole("button", { name: /^Try 2/ })).toBeVisible(); // the original's tries are as they were
  await expect(page.getByRole("button", { name: /^Try 3/ })).toHaveCount(0);

  // The offer shows the follow-up has now been attempted, not as new.
  await expect(page.locator("section").filter({ has: heading })).toContainText(/Answered 1 time before in this app/);
});
