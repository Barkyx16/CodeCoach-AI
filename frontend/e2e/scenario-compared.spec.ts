import AxeBuilder from "@axe-core/playwright";

import { chooseJob, expect, setTheme, test, type Page } from "./fixtures";

/**
 * Scenario runs compared with the run before by the one contract (Volume 20, prompt 2), against the
 * real API: a nurse finishes "Two call lights at once" on the imperfect path, then again on the
 * strong path. The second run's debrief sets both results side by side, says the runs took different
 * paths (so the decisions, not the counts, compare) and links to the first run, whose debrief says it's
 * the first. History's row says the same. axe finds nothing on the comparison in either theme.
 */
const cont = (page: Page) => page.getByRole("button", { name: "Continue" });
async function choose(page: Page, label: RegExp) {
  await page.getByLabel(label).check();
  await page.getByRole("button", { name: "Confirm this decision" }).click();
}
const SBAR =
  "Situation: bed 3 is short of breath and his saturation is dropping. Background: day 1 after hip surgery. " +
  "Assessment: I'm worried he's deteriorating. Recommendation: please come and see him now.";

async function begin(page: Page) {
  await page.goto("/scenarios/rn-two-patients");
  await page.getByRole("button", { name: "Start the scenario" }).click();
  await expect(page).toHaveURL(/\/scenarios\/attempts\//);
}

test("a second run on another path is partly comparable with the first, and says why", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`scen-cmp-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // The first run: bed 7 first, then waiting.
  await begin(page);
  await cont(page).click();
  await cont(page).click();
  await choose(page, /Bed 7, because their medicine is due/);
  await cont(page).click();
  await cont(page).click();
  await choose(page, /Recheck him in 30 minutes/);
  await cont(page).click();
  await page.getByLabel("Your response").fill("I would escalate earlier using SBAR because his breathing and saturation were getting worse.");
  await page.getByRole("button", { name: "Send response" }).click();
  const first = page.getByRole("region", { name: "Debrief" });
  await expect(first).toContainText("Escalation delayed (simulated)");
  await expect(first).toContainText("Not compared: the first finished run of this scenario");
  const firstUrl = new URL(page.url()).pathname;

  // The second run: bed 3 first, then the call.
  await begin(page);
  await cont(page).click();
  await cont(page).click();
  await choose(page, /Bed 3, and ask a colleague/);
  await cont(page).click();
  await choose(page, /Follow the unit protocol/);
  await page.getByLabel("Your response").fill(SBAR);
  await page.getByRole("button", { name: "Send response" }).click();
  const debrief = page.getByRole("region", { name: "Debrief" });
  await expect(debrief).toContainText("Escalated promptly (simulated)");
  const compared = debrief.getByRole("region", { name: "Compared with your previous attempt" });
  await expect(compared).toContainText("0 strong, 0 acceptable, 2 risky · ended: Escalation delayed (simulated)");
  await expect(compared).toContainText("This one: 2 strong, 0 acceptable, 0 risky · ended: Escalated promptly (simulated)");
  await expect(compared).toContainText("Partly comparable: the runs took different paths");
  await expect(compared).toContainText("set the decisions side by side, not the counts");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".submission-compared").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }
  const secondUrl = new URL(page.url()).pathname;

  // History says the same of both; the link opens the first run.
  await page.goto("/history");
  await expect(page.locator(`a.activity-row[href="${secondUrl}"]`)).toContainText("Partly comparable with the one before");
  await expect(page.locator(`a.activity-row[href="${firstUrl}"]`)).toContainText("Not compared: the first finished run of this scenario");
  await page.goto(secondUrl);
  await page.getByRole("link", { name: "Open that run" }).click();
  await expect(page).toHaveURL(new RegExp(`${firstUrl}$`));
  await expect(page.getByRole("region", { name: "Debrief" })).toContainText("Escalation delayed (simulated)");
});
