import { expect, test } from "@playwright/test";

// A nurse signs up, practices nursing interview questions and gets rubric feedback: the whole
// non-coding path against the real backend.
test("a nurse picks their job at sign-up, answers a question and gets feedback", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`nurse-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();

  // Signing up lands on a dashboard built from the nurse's own questions, not coding problems.
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText("of 300 questions")).toBeVisible();
  await page.getByRole("link", { name: "Practice questions" }).click();

  await expect(page.getByRole("heading", { name: "Registered Nurse interview questions" })).toBeVisible();
  const tabs = page.getByRole("tablist", { name: "Difficulty" });
  await expect(tabs.getByRole("tab", { name: "Easy 100" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("region", { name: "Question list" }).getByRole("listitem")).toHaveCount(5);

  // Search in plain words; the hard tab has matches too.
  await page.getByRole("searchbox", { name: "Search questions" }).fill("medication error");
  await tabs.getByRole("tab", { name: /Medium/ }).click();
  await page.getByRole("link", { name: /Patient assessment under pressure|medication/i }).first().click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  await page.getByLabel("Your answer", { exact: true }).fill(
    "Last winter, while I was working nights, a patient's oxygen dropped during my 2 a.m. assessment. I was " +
    "responsible for five patients, so I had to move fast. I checked his vital signs again and started oxygen per " +
    "protocol. I called the rapid response team and asked the charge nurse to cover my other patients. I updated " +
    "the doctor and documented everything in the electronic health record. As a result, he was stable within 30 " +
    "minutes. I learned to escalate early instead of waiting to be sure.",
  );
  await page.getByRole("button", { name: "Get feedback" }).click();
  const feedback = page.getByRole("region", { name: "Feedback" });
  await expect(feedback.getByLabel(/Score \d+ out of 100/)).toBeVisible();
  await expect(feedback.getByText("A strong answer includes")).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/careers-feedback.png", fullPage: true });

  // The answer shows up in the list as answered.
  await page.getByRole("link", { name: /Registered Nurse questions/ }).click();
  await expect(page.getByText(/1 answered/)).toBeVisible();

  // A mock interview made of nursing questions: answer one, skip the rest, get a summary.
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Interview" }).click();
  await expect(page.getByRole("heading", { name: "Registered Nurse interview" })).toBeVisible();
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page.getByText(/REGISTERED NURSE INTERVIEW · QUESTION 1 OF 5/)).toBeVisible();
  await page.getByLabel("Your answer", { exact: true }).fill(
    "I want to be a nurse because I care about patients and I am calm under pressure. In my last clinical " +
    "placement I looked after four patients and kept every assessment on time.",
  );
  await page.getByRole("button", { name: "Next question" }).click();
  for (let n = 2; n <= 5; n++) {
    await expect(page.getByText(new RegExp(`QUESTION ${n} OF 5`))).toBeVisible();
    await page.getByRole("button", { name: "Skip" }).click();
  }
  await expect(page.getByRole("heading", { name: "Registered Nurse interview results" })).toBeVisible();
  await expect(page.getByText(/Average score \d+\/100 across 1 of 5 answers/)).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/careers-interview-results.png", fullPage: true });
});
