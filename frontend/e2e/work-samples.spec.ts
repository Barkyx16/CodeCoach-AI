import AxeBuilder from "@axe-core/playwright";

import { expect, test, type APIRequestContext, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Work samples (Volume 10, prompt 5) against the real API: from the dashboard to a brief, an
 * incident update written by keyboard, feedback that quotes it and flags an invented time, a
 * revision that keeps the first attempt, the reply-to-a-customer format, and no accessibility
 * violations in either theme. Synthetic account.
 */
const PASSWORD = "CorrectHorse42";

async function signedIn(page: Page, request: APIRequestContext): Promise<void> {
  const email = `ws-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const r = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD, career_track: "software-engineer" } });
  expect(r.status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

test("an incident update by keyboard, feedback tied to its sentences, a revision, and a second format", async ({ page, request }) => {
  await signedIn(page, request);
  await page.goto("/dashboard");
  await page.getByRole("link", { name: /^Work samples/ }).click();
  await page.getByRole("region", { name: "For your career" }).getByRole("link", { name: "Checkout errors: the first status update" }).click();
  await expect(page.getByRole("region", { name: "The brief" })).toContainText("About 30% of checkout attempts fail");

  await page.getByLabel(/^What's happening/).focus();
  await page.keyboard.type("Since 09:12 UTC some card payments at checkout are failing. It is fixed now.");
  await page.keyboard.press("Tab");
  await page.keyboard.type("Some customers, since 14:00. Browsing and search still work.");
  await page.keyboard.press("Tab");
  await page.keyboard.type("We are investigating with the payment provider. Customers can retry or use a gift card.");
  await page.keyboard.press("Tab");
  await page.keyboard.type("Next update at 10:30 UTC.");
  for (const theme of ["dark", "light"]) {
    await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
    const scan = await new AxeBuilder({ page }).include(".ws-layout").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("heading", { name: /^Feedback on/ })).toBeFocused();
  const flags = page.getByRole("region", { name: "Not supported by the brief" });
  await expect(flags).toContainText("“fixed” in It is fixed now.");
  await expect(flags).toContainText("“14:00”");
  await expect(page.getByRole("region", { name: "Missing" })).toContainText("Who is affected, and how much");

  await page.getByLabel(/^What's happening/).fill("Since 09:12 UTC some card payments at checkout are failing.");
  await page.getByLabel(/^Who is affected/).fill("About 30% of checkout attempts fail. Browsing, search and gift-card payments still work.");
  await page.getByRole("button", { name: "Send the revision for feedback" }).click();
  await expect(page.getByText("Sent as a revision. Your earlier attempt is kept as it was.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Required parts" })).toContainText("Covers 6 of the 6 points");
  await expect(page.getByRole("region", { name: "Your attempts" }).getByRole("listitem")).toHaveCount(2);

  // A second format: a reply to a customer, one plain message.
  await page.goto("/work-samples/ws-billing-explanation");
  await page.getByLabel(/^Your message/).fill(
    "Dear Ms Okafor, I'm sorry we charged you twice for March. We refunded the extra $84.20 on 6 April; it takes 3 to 5 business days. "
    + "Your account is up to date. Reply to this email or call 0800 555 0199 and quote TW-48213.",
  );
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: "Required parts" })).toContainText("Covers 6 of the 6 points");
  await expect(page.getByRole("region", { name: "Not supported by the brief" })).toHaveCount(0);
});
