import AxeBuilder from "@axe-core/playwright";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

/**
 * The portfolio demo from a fresh disposable database (Volume 7, prompt 10), on desktop and on a
 * phone: the guided path (a question, a short interview that resumes after a reload, progress),
 * a second visitor who can't see the first one's work, the honest "no judge" and "built-in coach"
 * states, and no email. Screenshots go to e2e-demo/screenshots/<project>-*.png.
 */
const offset = Number(process.env.E2E_PORT_OFFSET ?? "50");
const API = `http://localhost:${8000 + offset}`;
const backend = fileURLToPath(new URL("../../backend/", import.meta.url));
const ANSWER =
  "I start with airway, breathing and circulation, then a full set of vital signs. Last month a patient's breathing " +
  "rate rose, so I rechecked, raised it with the nurse in charge and called the doctor. As a result we started oxygen early.";

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => v.id), where).toEqual([]);
}
const shot = (page: Page, name: string) =>
  page.screenshot({ path: `e2e-demo/screenshots/${test.info().project.name}-${name}.png`, fullPage: true });

test("the guided path: a question, an interview that resumes, progress", async ({ page }) => {
  // Each run starts from the same reset state (the API wouldn't have started otherwise).
  expect(readFileSync(`${backend}e2e-demo-fingerprint-${offset}.txt`, "utf8")).toMatch(/^Starting-state fingerprint: [0-9a-f]{64}\n$/);

  await page.goto("/");
  await expect(page.getByRole("note")).toContainText("This is a demo with fictional data.");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/\/demo$/);
  const caps = page.getByRole("region", { name: "What this demo server can do right now" });
  await expect(caps).toContainText("isn't connected to a code judge"); // the honest unavailable state
  await expect(caps).toContainText("No AI service is called");
  await expect(page.getByRole("region", { name: /Sam Rivera/ })).toContainText("(fictional) · Registered Nurse");
  await page.getByText("Sam Rivera's example answers (2)").click();
  await expect(page.getByRole("article").first()).toContainText("Example. Example answer, written for this demo by a fictional learner.");
  await axe(page, "/demo");
  await shot(page, "demo-entry");

  // A question, with feedback, and the way back.
  await page.getByRole("button", { name: "Start a demo session as a registered nurse" }).click();
  await expect(page.getByRole("heading", { name: "Your approach to patient assessment", level: 1 })).toBeVisible();
  await page.getByLabel("Your answer", { exact: true }).fill(ANSWER);
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: "Feedback" })).toBeVisible();
  await shot(page, "demo-feedback");
  await page.getByRole("link", { name: "Back to the demo" }).click();
  await expect(page.getByRole("heading", { name: "Things to try (about ten minutes)" })).toBeVisible();

  // A short interview that survives a reload, draft included.
  await page.getByRole("link", { name: "Run a short mock interview" }).click();
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page.getByText(/QUESTION 1 OF 5/)).toBeVisible();
  await page.getByLabel("Your answer", { exact: true }).fill(ANSWER);
  await page.getByRole("button", { name: "Next question" }).click();
  await expect(page.getByText(/QUESTION 2 OF 5/)).toBeVisible();
  await page.getByLabel("Your answer", { exact: true }).fill("A draft I'm still writing");
  await page.reload();
  await expect(page.getByText(/QUESTION 2 OF 5/)).toBeVisible();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue("A draft I'm still writing");

  // Progress, from what this visitor did.
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator("main")).toContainText(/answered|Answered/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  await shot(page, "demo-dashboard");
});

test("a second visitor sees none of the first one's work, and can't make an account", async ({ browser }) => {
  const first = await browser.newContext();
  const a = await first.newPage();
  await a.goto("/demo");
  await a.getByRole("button", { name: "Start a demo session as a registered nurse" }).click();
  await a.getByLabel("Your answer", { exact: true }).fill(`${ANSWER} Only the first visitor wrote this.`);
  await a.getByRole("button", { name: "Get feedback" }).click();
  await expect(a.getByRole("region", { name: "Feedback" })).toBeVisible();
  const question = a.url();

  const second = await browser.newContext();
  const b = await second.newPage();
  await b.goto("/demo");
  await b.getByRole("button", { name: "Start a demo session as a registered nurse" }).click();
  await b.goto(question);
  await expect(b.getByRole("heading", { name: "Your approach to patient assessment", level: 1 })).toBeVisible();
  await expect(b.getByText("Only the first visitor wrote this.")).toHaveCount(0);
  await expect(b.getByRole("heading", { name: "Your past answers" })).toHaveCount(0);
  await b.goto("/history");
  await expect(b.getByText("Only the first visitor wrote this.")).toHaveCount(0);

  await b.goto("/register");
  await expect(b.getByRole("heading", { name: "Accounts can't be created on this demo" })).toBeVisible();
  const refused = await b.request.post(`${API}/api/v1/auth/register`, { data: { email: "visitor@example.com", password: "CorrectHorse42" } });
  expect(refused.status()).toBe(403);
  expect((await refused.json()).error.code).toBe("demo_mode");
  await first.close();
  await second.close();
});

test("a coding visitor: the built-in coach, and a submission that says it wasn't run", async ({ page }) => {
  await page.goto("/demo");
  await page.getByRole("button", { name: "Start a demo session as a software engineer" }).click();
  await page.getByRole("link", { name: "Back to the demo" }).click();
  await page.getByRole("link", { name: "Open a coding problem" }).click();
  await expect(page.getByRole("heading", { name: "Two Sum", level: 1 })).toBeVisible();
  const tabs = page.getByRole("tablist", { name: "Workspace" }); // a phone shows one panel at a time
  if (await tabs.isVisible()) await tabs.getByRole("tab", { name: "Code" }).click();
  await expect(page.getByText("Code can't run on this server.")).toBeVisible();
  await page.getByRole("button", { name: /^Save attempt/ }).click();
  await expect(page.getByText(/Saved, but not run yet/)).toBeVisible(); // never a made-up verdict
  await expect(page.getByText(/Accepted|All tests passed/)).toHaveCount(0);
  if (await tabs.isVisible()) await tabs.getByRole("tab", { name: "Coach" }).click();
  await page.getByRole("button", { name: "Get a hint" }).click();
  await expect(page.getByRole("region", { name: "AI coach" })).toContainText(/Built-in coach/);
  await expect(page.getByRole("button", { name: "Unlock level 2: Concept" })).toBeVisible();
  await page.waitForTimeout(400); // let the buttons' colour transition finish before the screenshot
  await shot(page, "demo-coding");
});

test.afterAll(() => {
  // No email left this demo server: nothing was even written to its local outbox.
  const outbox = `${backend}e2e-demo-outbox-${offset}`;
  expect(existsSync(outbox) ? readdirSync(outbox) : []).toEqual([]);
});
