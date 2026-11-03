import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "./fixtures";

// The optional first session against the real API: a welcome with a real activity from the
// learner's own job, a tour of the real page that can be left and resumed, and Help.

const ANSWER = "First I check airway, breathing and circulation, then a full set of vital signs. I compare them with the last observations, ask the patient how they feel, check pain and wounds, and escalate to the doctor using SBAR if anything has changed. Then I document it.";

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })), where).toEqual([]);
}

const tour = (page: Page) => page.getByRole("region", { name: "Introduction" });

/** The element a step explains sits fully above the docked panel: nothing is hidden behind it. */
async function notCovered(page: Page, selector: string) {
  // Polled: the page may still be scrolling the element into view.
  await expect.poll(async () => {
    const [box, panel] = await Promise.all([page.locator(selector).boundingBox(), tour(page).boundingBox()]);
    return !!box && !!panel && box.y >= 0 && box.y + box.height <= panel.y + 1;
  }, { message: `${selector} is fully above the tour panel` }).toBe(true);
}

test("a new nurse is welcomed, tours a real nursing question, gets real feedback, and isn't welcomed twice", async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
  const email = `welcome-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();

  await expect(page).toHaveURL(/\/welcome$/);
  const main = page.locator("#main");
  await expect(main.getByText("You're practising for")).toContainText("Registered Nurse");
  await expect(main.getByText(/built-in rubric coach/)).toBeVisible();
  await expect(main.getByText(/java/i)).toHaveCount(0);
  await axe(page, "welcome");
  await page.getByRole("button", { name: "Start the tour" }).click();

  // The tour explains the real question page; its heading takes focus.
  await expect(page).toHaveURL(/\/careers\/registered-nurse\/questions\//);
  await expect(tour(page).getByRole("heading", { name: "Read the question" })).toBeFocused();
  await expect(page.locator('[data-tour="question"]')).toHaveAttribute("data-tour-active", "");
  await axe(page, "question page with the tour");
  await tour(page).getByRole("button", { name: "Next" }).press("Enter"); // keyboard
  await expect(tour(page).getByRole("heading", { name: "Your answer" })).toBeFocused();
  await notCovered(page, "#answer-text");

  // A real answer, while the tour is open: nothing is blocked.
  await page.getByRole("textbox", { name: "Your answer" }).fill(ANSWER);
  await tour(page).getByRole("button", { name: "Next" }).click();
  await tour(page).getByRole("button", { name: "Next" }).click();
  await expect(tour(page).getByRole("heading", { name: "Getting feedback" })).toBeVisible();
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: "Feedback" })).toBeVisible();
  await tour(page).getByRole("button", { name: "Next" }).click();
  await expect(tour(page).getByRole("heading", { name: "What to do next" })).toBeVisible();
  await expect(page.locator('[data-tour="next"]')).toHaveAttribute("data-tour-active", "");
  await tour(page).getByRole("button", { name: "Finish" }).click();
  await expect(tour(page)).toHaveCount(0);
  await expect(page.locator("#main")).toBeFocused();

  // The dashboard has nothing more to say; the answer counts, the tour didn't.
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Getting started" })).toHaveCount(0);

  // A returning sign-in goes to the dashboard, not the welcome.
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // Help: searchable, and the tour can be replayed from it.
  await page.getByRole("link", { name: "Help" }).click();
  await page.getByLabel("Search help").fill("drafts");
  await expect(page.getByText("Is my answer saved while I type?")).toBeVisible();
  await expect(page.getByText("You finished the introduction.")).toBeVisible();
  await axe(page, "help");
});

test("a coding guest tours the workspace, leaves, resumes after a reload, and can dismiss the reminder", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/\/welcome$/);
  await expect(page.getByText("Two Sum")).toBeVisible();
  await page.getByRole("button", { name: "Start the tour" }).click();

  await expect(page).toHaveURL(/\/problems\/two-sum$/);
  await expect(tour(page).getByRole("heading", { name: "The problem" })).toBeFocused();
  await tour(page).getByRole("button", { name: "Next" }).click();
  await expect(tour(page).getByRole("heading", { name: "The editor" })).toBeVisible();
  await expect(tour(page)).toContainText("Ctrl+M");

  // A reload resumes at the same step.
  await page.reload();
  await expect(tour(page).getByRole("heading", { name: "The editor" })).toBeVisible();
  await expect(tour(page)).toContainText("step 2 of 5");
  await tour(page).getByRole("button", { name: "Next" }).click();
  await tour(page).getByRole("button", { name: "Next" }).click();
  await expect(tour(page).getByRole("heading", { name: "Checking your code" })).toBeVisible();
  await notCovered(page, '[data-tour="submit"]');

  await tour(page).getByRole("button", { name: "Leave the introduction" }).click();
  await expect(tour(page)).toHaveCount(0);
  await page.getByRole("link", { name: "Dashboard" }).click();
  const banner = page.getByRole("region", { name: "Getting started" });
  await expect(banner).toContainText("You left the introduction at step 4 of 5.");
  await banner.getByRole("button", { name: "Resume" }).click();
  await expect(page).toHaveURL(/\/problems\/two-sum$/);
  await expect(tour(page).getByRole("heading", { name: "Checking your code" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(tour(page)).toHaveCount(0);

  await page.goto("/dashboard");
  await page.getByRole("region", { name: "Getting started" }).getByRole("button", { name: "Dismiss" }).click();
  await expect(page.getByRole("region", { name: "Getting started" })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Getting started" })).toHaveCount(0);
});

test("a guest can switch job on the welcome, and the tour works at 320px in the light theme", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "light" })));
  await page.setViewportSize({ width: 320, height: 640 });
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/\/welcome$/);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Change job" }).click();
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.getByRole("button", { name: "Use this job" }).click();
  await expect(page.locator("#main").getByText("You're practising for")).toContainText("Registered Nurse");
  await expect(page.getByRole("heading", { name: "Answer one question now" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, "welcome at 320px, light");

  await page.getByRole("button", { name: "Start the tour" }).click();
  await expect(tour(page).getByRole("heading", { name: "Read the question" })).toBeVisible();
  await tour(page).getByRole("button", { name: "Next" }).click();
  await expect(tour(page).getByRole("heading", { name: "Your answer" })).toBeVisible();
  await notCovered(page, "#answer-text");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, "tour at 320px, light");
  // Every control on the page can still be scrolled clear of the panel.
  await page.getByRole("button", { name: "Get feedback" }).scrollIntoViewIfNeeded();
  await notCovered(page, '[data-tour="feedback"]');
});
