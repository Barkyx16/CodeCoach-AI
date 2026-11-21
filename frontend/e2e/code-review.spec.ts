import AxeBuilder from "@axe-core/playwright";

import { expect, test, type APIRequestContext, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Code-review practice (Volume 10, prompt 3) against the real API: reached from the coding
 * library, a finding written by keyboard, an unsaved draft that survives a reload, a sent review
 * compared with the authored one (the real defect with its public-test evidence, the style point
 * labelled a preference), and the review kept with the version it reviewed. Synthetic account.
 */
const PASSWORD = "CorrectHorse42";

async function signedIn(page: Page, request: APIRequestContext): Promise<void> {
  const email = `review-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const r = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD, career_track: "software-engineer" } });
  expect(r.status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

test("review someone else's code: a finding by keyboard, a draft through a reload, then the comparison", async ({ page, request }) => {
  await signedIn(page, request);
  await page.goto("/problems");
  await page.getByRole("link", { name: "Code review: review someone else's code" }).click();
  await page.getByRole("link", { name: "Review: Largest Number" }).click();
  await expect(page.getByText("CODE REVIEW · YOU'RE THE REVIEWER")).toBeVisible();
  await expect(page.getByLabel(/^The code under review/)).toContainText("int largest = 0;");
  await expect(page.getByText("The running maximum starts at 0")).toHaveCount(0);

  // Keyboard only: add a finding, cite line 7, describe it.
  await page.getByRole("button", { name: "Add a finding" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("From line")).toBeFocused();
  await page.keyboard.type("7");
  await expect(page.getByLabel("The code at line 7")).toContainText("int largest = 0;");
  await page.keyboard.press("Tab"); // To line (empty: the same line)
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("What's wrong")).toBeFocused();
  await page.keyboard.type("The maximum starts at 0, so negative values never replace it.");
  await page.getByLabel(/^What happens because of it/).fill("Public test 2, [-5, -2, -11], returns 0 instead of -2.");
  await expect(page.getByText("Unsaved changes, kept on this device")).toBeVisible();

  // A reload before saving: the work is offered back from this device.
  await page.reload();
  await page.getByRole("region", { name: "Unsaved changes" }).getByRole("button", { name: "Restore them" }).click();
  await expect(page.getByLabel("What's wrong")).toHaveValue(/starts at 0/);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Saved to your account.")).toBeVisible();
  const scan = await new AxeBuilder({ page }).include(".review-layout").analyze();
  expect(scan.violations.map((v) => v.id)).toEqual([]);

  await page.getByRole("button", { name: "Send review and compare" }).click();
  await expect(page.getByRole("heading", { name: "Your review and the authored one" })).toBeFocused();
  const yours = page.getByRole("region", { name: "Your findings" });
  await expect(yours.getByText("Points at an authored defect")).toBeVisible();
  const reference = page.getByRole("region", { name: "The authored review" });
  await expect(reference).toContainText("Public test 2: nums = [-5, -2, -11] should give -2; this code returns 0.");
  await expect(reference).toContainText("Observation · a preference, not a defect");
  await expect(reference).toContainText("In your review: finding 1.");
  await expect(page.getByRole("region", { name: "How your review compares" })).toContainText("The authored review has one defect, shown by a public test. Your review points at it.");

  // The review is kept with the code it reviewed.
  await page.getByRole("region", { name: "Your earlier reviews" }).getByRole("link").first().click();
  await expect(page.getByLabel(/^The code you reviewed \(version 1\)/)).toContainText("int largest = 0;");
});

test("a correct implementation: saying there's no defect is a complete review", async ({ page, request }) => {
  await signedIn(page, request);
  await page.goto("/code-reviews/review-binary-search");
  await page.getByLabel(/^Summary \(optional\)/).fill("This looks correct; (lo + hi) / 2 can't overflow at these sizes.");
  await page.getByRole("button", { name: "Send review and compare" }).click();
  const compares = page.getByRole("region", { name: "How your review compares" });
  await expect(compares).toContainText("The authored review found no defect in this code");
  await expect(compares).toContainText("agrees there's no defect");
  await expect(page.getByRole("region", { name: "The authored review" })).not.toContainText("Defect · shown by a public test");
});
