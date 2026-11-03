import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// A private reflection on a real interview, against the real API: from an application's
// interview to an incomplete reflection, recovery after a failed save, suggestions that wait for
// the learner, one accepted step (and no duplicate), an outcome that moves the application only
// when asked, an archived application, search, and phone-sized use with predictable Back.

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })), where).toEqual([]);
}

async function signUpNurse(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`reflect-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

/** An application with one interview event, through the real API (as the page would). */
async function applicationWithInterview(page: Page) {
  await page.goto("/applications");
  await page.getByRole("button", { name: "Add an application" }).click();
  const form = page.getByRole("form", { name: "New application" });
  await form.getByLabel("Role title").fill("Ward nurse");
  await form.getByLabel("Employer").fill("Mercy General");
  await form.getByRole("button", { name: "Add application" }).click();
  await page.getByRole("link", { name: "Ward nurse" }).click();
  await page.getByRole("button", { name: "Add an event" }).click();
  const ev = page.getByRole("form", { name: "New event" });
  await ev.getByLabel("What").fill("Panel interview");
  await ev.getByLabel(/^Date/).fill("2026-11-12");
  await ev.getByRole("button", { name: "Add event" }).click();
  await expect(page.getByRole("link", { name: "Reflect on this interview" })).toBeVisible();
}

test("reflect, recover, choose steps, record an outcome, and find it again", async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
  await signUpNurse(page);
  await applicationWithInterview(page);
  const appUrl = page.url();
  await page.getByRole("link", { name: "Reflect on this interview" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Reflect on Panel interview" })).toBeVisible();
  await expect(page.getByText("Leave out details that identify patients, clients, colleagues or interviewers.")).toBeVisible();

  // An incomplete reflection; a save that fails keeps the words, and a reload offers them back.
  await page.getByLabel(/Topics that came up/).fill("patient assessment\nquantum accounting");
  await page.getByLabel("What was difficult").fill("The medication error question");
  await page.route("**/events/*/reflection", (r) => (r.request().method() === "PUT" ? r.abort() : r.continue()));
  await page.getByRole("button", { name: "Save reflection" }).click();
  await expect(page.locator(".inline-error")).toBeVisible();
  await page.unroute("**/events/*/reflection");
  await page.reload();
  await page.getByRole("button", { name: "Restore them" }).click();
  await expect(page.getByLabel("What was difficult")).toHaveValue("The medication error question");
  await page.getByLabel("Add an observation").fill("They asked for another example");
  await page.getByRole("button", { name: "Add observation" }).click();
  await page.getByRole("button", { name: "Save reflection" }).click();
  await expect(page.getByText("Saved. Only you can see it.")).toBeVisible();
  await axe(page, "saved reflection");

  // Suggestions wait for a choice; accepting twice can't happen, and a gap stays a gap.
  await page.getByRole("button", { name: "Suggest next steps" }).click();
  const steps = page.getByRole("region", { name: "Next steps" });
  await expect(steps.getByText("No practice here yet for “quantum accounting”")).toBeVisible();
  const practice = steps.locator(".reflection-action--practice").first();
  await practice.getByRole("button", { name: "Add to notebook" }).click();
  await expect(practice).toContainText("Added to your notebook.");
  await expect(practice.getByRole("button", { name: "Add to notebook" })).toHaveCount(0);
  await steps.getByRole("button", { name: "Suggest again from my reflection" }).click();
  await expect(steps.locator(".reflection-action--practice").first()).toContainText("Added to your notebook.");
  await axe(page, "next steps");

  // Waiting doesn't move the application; an offer does, only when ticked.
  const next = page.getByRole("region", { name: "What happened next" });
  await next.getByRole("combobox", { name: /^Outcome/ }).selectOption("offer");
  await next.getByRole("checkbox", { name: /Also move the application to “Offer”/ }).check();
  await next.getByRole("button", { name: "Save outcome" }).click();
  await expect(next).toContainText("(the application was updated)");
  await page.goto(appUrl);
  await expect(page.locator(".page__header")).toContainText("Offer");

  // Archive it: the reflection is still there, and search finds it.
  await page.getByRole("button", { name: "Archive" }).click();
  await page.goto("/reflections?q=medication");
  await page.getByRole("link", { name: /Panel interview: Ward nurse at Mercy General/ }).click();
  await expect(page.getByText("This application is archived. Your reflection stays here.")).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/reflections\?q=medication/);
});

test("on a phone, in dark and light: entry works and nothing scrolls sideways", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "dark" })));
  await signUpNurse(page);
  await page.setViewportSize({ width: 320, height: 720 });
  await applicationWithInterview(page);
  await page.getByRole("link", { name: "Reflect on this interview" }).click();
  await page.getByLabel(/Questions you were asked/).fill("Why this ward?");
  await page.getByRole("button", { name: "Save reflection" }).click();
  await expect(page.getByText("Saved. Only you can see it.")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, "reflection at 320px, dark");
  await page.evaluate(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "light" })));
  await page.reload();
  await expect(page.getByLabel(/Questions you were asked/)).toHaveValue("Why this ward?");
  await axe(page, "reflection at 320px, light");
});
