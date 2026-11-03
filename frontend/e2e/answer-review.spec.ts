import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Rubric transparency against the real API: criteria before answering, an optional reflection
// that holds the feedback, quoted evidence, "different perspectives", a private flag, an honest
// "checking again wouldn't change anything", the insufficient-evidence state, and narrow and
// themed screens.

const QUESTION = "/careers/registered-nurse/questions/m-walk-1";
const STRONG =
  "Last month a daughter was angry that her father had waited two hours for pain relief on our ward. I was the nurse " +
  "responsible for him that shift, so I took her to a quiet room and listened without interrupting. I apologised for the " +
  "wait, explained that the prescription had needed a doctor's review, and called the doctor while she was with me. I " +
  "checked back within 30 minutes with his pain score down from 8 to 3. She thanked the team, and I learned to explain " +
  "delays early instead of waiting for families to ask.";

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })), where).toEqual([]);
}

async function signUpNurse(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`review-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("criteria first, a reflection before the feedback, quoted evidence, perspectives and a private flag (keyboard)", async ({ page }) => {
  await signUpNurse(page);
  await page.goto(QUESTION);
  const criteria = page.locator(".criteria-panel");
  await criteria.locator("summary").focus();
  await page.keyboard.press("Enter");
  await expect(criteria.getByRole("heading", { name: "Points the coach looks for in your words" })).toBeVisible();
  await expect(criteria.getByRole("heading", { name: "Fixed checks, the same for every answer" })).toBeVisible();
  await expect(criteria).toContainText("not an employer's rubric");

  await page.getByRole("checkbox", { name: /Reflect on my answer before seeing the feedback/ }).check();
  await page.getByRole("textbox", { name: "Your answer" }).fill(STRONG);
  const sent = page.waitForResponse((r) => r.url().includes("/questions/m-walk-1/answers") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Get feedback" }).press("Enter");
  const { id: answerId } = (await (await sent).json()) as { id: string };
  const gate = page.getByRole("form", { name: "Before you read the feedback" });
  await expect(gate).toBeVisible();
  await expect(page.getByRole("region", { name: "Feedback" })).toHaveCount(0);
  await gate.getByLabel("What went well?").fill("I explained the delay and followed up.");
  const firstGroup = gate.getByRole("radiogroup").first();
  await firstGroup.getByRole("radio", { name: "Yes" }).check();
  await axe(page, "self-review before feedback");
  await gate.getByRole("button", { name: "Save and show feedback" }).press("Enter");

  const feedback = page.getByRole("region", { name: "Feedback" });
  await expect(feedback).toBeVisible();
  await expect(feedback.locator(".feedback-card__evidence").first()).toContainText("From your answer:");
  const quoted = (await feedback.locator(".feedback-card__evidence").first().innerText()).replace(/^From your answer: “|”$/g, "");
  expect(STRONG).toContain(quoted); // the excerpt is the learner's own words
  const table = page.getByRole("table", { name: "Your ratings beside what the coach found" });
  await expect(table).toBeVisible();
  await expect(page.getByText("Written before you read the feedback.")).toBeVisible();

  await expect(page.getByText(/same result for the same answer/)).toBeVisible();
  await page.getByRole("button", { name: "Flag “the feedback overall”" }).press("Enter");
  await page.getByRole("radio", { name: "It's unclear" }).check();
  await page.getByLabel("Private note (optional)").fill("Which part counts as the result?");
  await page.getByRole("button", { name: "Save flag" }).press("Enter");
  await expect(page.getByText("Unclear to you")).toBeVisible();
  await axe(page, "feedback with reflection and a flag");

  // The reflection and the flag stay with the answer (opened the way History links to it).
  await page.goto(`${QUESTION}?answer=${answerId}`);
  await page.getByText("Your reflection, flags and checking again").click();
  await expect(page.getByText("I explained the delay and followed up.")).toBeVisible();
  await expect(page.getByText("Unclear to you")).toBeVisible();
});

test("an answer too short to evaluate shows no score; skipping the reflection costs nothing; 320px light and dark", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "dark" })));
  await signUpNurse(page);
  await page.goto(QUESTION);
  await page.getByRole("checkbox", { name: /Reflect on my answer before seeing the feedback/ }).check();
  await page.getByRole("textbox", { name: "Your answer" }).fill("I listened to her and called the doctor.");
  await page.getByRole("button", { name: "Get feedback" }).click();
  await page.getByRole("button", { name: "Skip and show feedback" }).click();
  const feedback = page.getByRole("region", { name: "Feedback" });
  await expect(feedback.getByLabel("Not enough to score yet")).toBeVisible();
  await axe(page, "insufficient evidence, dark");

  await page.evaluate(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "light" })));
  await page.setViewportSize({ width: 320, height: 700 });
  await page.reload();
  await page.getByText("How your answer is evaluated").click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, "criteria at 320px, light");
});
