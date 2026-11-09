import AxeBuilder from "@axe-core/playwright";

import { expect, test, type APIRequestContext, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Comparing sample answers (Volume 10, prompt 6) against the real API: from the dashboard to a
 * lesson, both samples side by side, excerpts marked by keyboard with a reason each, a choice,
 * results in words tied to the explanation's quotes, the reading kept in the list, a tradeoff lesson
 * without a choice, and no accessibility violations in either theme. Synthetic account.
 */
const PASSWORD = "CorrectHorse42";

async function signedIn(page: Page, request: APIRequestContext): Promise<void> {
  const email = `cmp-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const r = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD, career_track: "software-engineer" } });
  expect(r.status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

test("a lesson by keyboard: marks with reasons, a choice, and results tied to the explanation", async ({ page, request }) => {
  await signedIn(page, request);
  await page.goto("/dashboard");
  await page.getByRole("link", { name: /^Compare sample answers/ }).click();
  await page.getByRole("link", { name: "Specific evidence or general claims" }).click();
  const a = page.getByRole("list", { name: "Answer A, sentence by sentence" });
  const b = page.getByRole("list", { name: "Answer B, sentence by sentence" });
  await expect(a).toBeVisible();
  await expect(b).toBeVisible(); // side by side on a wide screen
  await expect(page.getByRole("region", { name: "The explanation", exact: true })).toHaveCount(0);

  // Mark by keyboard only: focus the button, press Space, then Tab into the reason that appears.
  await b.getByRole("listitem").nth(2).getByRole("button", { name: "Strength" }).focus();
  await page.keyboard.press("Space");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Why is it a strength?")).toBeFocused();
  await page.keyboard.type("It names exactly what they did: asked for time and brought examples.");
  await a.getByRole("listitem").nth(0).getByRole("button", { name: "Gap" }).focus();
  await page.keyboard.press("Enter");
  await expect(a.getByRole("listitem").nth(0).getByRole("button", { name: "Gap" })).toHaveAttribute("aria-pressed", "true");
  await page.getByLabel("Why is it a gap?").fill("A claim about yourself is not evidence of anything.");
  await page.getByRole("radio", { name: "Answer B" }).check();
  for (const theme of ["dark", "light"]) {
    await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
    const scan = await new AxeBuilder({ page }).include(".cmp-page").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }
  await page.getByRole("button", { name: "Compare with the explanation" }).click();
  await expect(page.getByRole("heading", { name: "Your reading and the explanation" })).toBeFocused();
  const compared = page.getByRole("list", { name: "Your marks compared with the explanation" });
  await expect(compared.getByText("Matches the explanation")).toHaveCount(2);
  await expect(compared).toContainText("I asked for 20 minutes with her and brought three examples");
  await expect(page.getByText(/as the explanation does/)).toBeVisible();
  const shown = page.getByRole("region", { name: "The explanation", exact: true });
  await expect(shown).toContainText("Not settled:");
  await expect(shown.getByRole("link", { name: "Try a communication drill" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Your earlier readings" }).getByRole("listitem")).toHaveCount(1);

  // A lesson with no single best answer asks for no choice.
  await page.goto("/compare/cmp-tradeoffs");
  await expect(page.getByRole("heading", { name: "No single best answer" })).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(0);
});
