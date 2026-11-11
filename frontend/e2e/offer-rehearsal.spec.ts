import AxeBuilder from "@axe-core/playwright";

import { expect, test, type APIRequestContext, type Page, setTheme } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Offer rehearsals (Volume 10, prompt 8) against the real API: from the dashboard to a fictional
 * card, the three parts by keyboard, the counterpart quoting the card and keeping unknowns
 * unknown, declining the counteroffer, a debrief with the card's own arithmetic, no accessibility
 * violations in either theme, and a different approach that keeps the first. Synthetic account.
 */
const PASSWORD = "CorrectHorse42";

async function signedIn(page: Page, request: APIRequestContext): Promise<void> {
  const email = `offer-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const r = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD, career_track: "it-support-specialist" } });
  expect(r.status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

async function say(page: Page, text: string) {
  await page.getByLabel("What you'd say").fill(text);
  await page.getByRole("button", { name: "Say it" }).click();
  await expect(page.getByRole("list", { name: "Transcript" })).toContainText(text);
}

test("three parts against a fictional card, a declined counteroffer, and a debrief with real arithmetic", async ({ page, request }) => {
  await signedIn(page, request);
  await page.goto("/dashboard");
  await page.getByRole("link", { name: /^Rehearse an offer conversation/ }).click();
  await page.getByRole("link", { name: "A first offer for a support analyst role" }).click();
  await expect(page.getByRole("region", { name: "The offer (fictional)" })).toContainText("Not stated in the offer (unknown)");
  await page.getByLabel("Goal 1").fill("A higher base salary");
  await page.getByRole("button", { name: "Start the rehearsal" }).click();
  await expect(page.getByText("Authored responses (no AI)")).toBeVisible();

  await say(page, "What's the base salary, and is there a bonus?");
  const transcript = page.getByRole("list", { name: "Transcript" });
  await expect(transcript).toContainText("Base salary: £31,000 per year.");
  await expect(transcript).toContainText("Bonus: That isn't set out in the offer you have.");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".offers-rehearsal").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }
  await page.getByRole("button", { name: "Move on: make a reasoned request" }).click();
  await say(page, "I'd like to ask for a base of £34,000, because I already hold the support certification the role asks for.");
  await expect(transcript).toContainText("I can't agree a different salary on this call.");
  await page.getByRole("button", { name: "Move on: respond to the counteroffer" }).click();
  await expect(transcript).toContainText("£32,500");
  await say(page, "Thank you for checking. I've thought about it and I'm going to decline the offer.");

  const debrief = page.getByRole("region", { name: "Debrief" });
  await expect(debrief.getByRole("heading", { name: "Debrief" })).toBeFocused();
  await expect(debrief).toContainText("£34,000 per year against the card's £31,000 per year: +£3,000 (+9.7%).");
  await expect(debrief).toContainText("You declined.");
  await expect(debrief).toContainText("Declining is a complete answer.");
  await expect(debrief).toContainText("Your goals (you wrote these): A higher base salary");
  await expect(debrief).toContainText("Training budget (not asked about");
  const first = page.url();
  await debrief.getByRole("button", { name: "Try a different approach" }).click();
  await expect(page.getByText("A different approach: your earlier rehearsal is kept")).toBeVisible();
  await page.goto(first);
  await expect(page.getByRole("region", { name: "Debrief" })).toContainText("You declined.");
});
