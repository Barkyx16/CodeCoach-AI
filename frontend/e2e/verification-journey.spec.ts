import fs from "node:fs";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";

import { chooseJob, expect, test, type Page } from "./fixtures";
import { E2E_OUTBOX } from "./ports";

/**
 * Email verification as a recovery journey, against the real API and its file capture transport
 * (EMAIL_BACKEND=file: emails are saved, never sent). This shows the journey works; it isn't
 * evidence that an email reaches a real inbox, which only an authorized live send can show.
 * - A learner heading for a page signs up, sees where the code went (masked) and that this server
 *   kept the email instead of sending it, and can't resend inside the server's cooldown;
 * - the link opened in a second tab confirms, the first tab moves on by itself, and both continue
 *   to the page the learner was going to;
 * - the same link again (pasted into the same tab), and a link cut short, say what they are;
 * - another account's link, opened while signed in, asks first and leaves that session alone.
 */
const PASSWORD = "CorrectHorse42";

function linkTokenFor(email: string): string | null {
  if (!fs.existsSync(E2E_OUTBOX)) return null;
  const mails = fs.readdirSync(E2E_OUTBOX).sort().map((f) => JSON.parse(fs.readFileSync(path.join(E2E_OUTBOX, f), "utf8")));
  return mails.filter((m) => m.to === email).at(-1)?.text.match(/\/verify-email#token=([\w-]+)/)?.[1] ?? null;
}

/** WCAG 2.1 A/AA (axe-core), as e2e/a11y.spec.ts checks the other screens. */
async function expectNoViolations(page: Page, view: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.help}`), `axe violations on ${view}`).toEqual([]);
}

async function signUp(page: Page, email: string) {
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await chooseJob(page, "software-engineer");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
}

test("signed up on the way to a page: masked status, a second tab confirms, both continue there", async ({ page: a }) => {
  const email = `journey-${Date.now()}@example.com`;
  await a.goto("/history");
  await expect(a).toHaveURL(/\/login$/);
  await a.getByRole("link", { name: "Create an account" }).click();
  await expect(a.getByRole("heading", { name: "Create your account" })).toBeVisible();
  await signUp(a, email);

  // Where it went, masked; what this server did with it; and the server's cooldown on resend.
  await expect(a.getByTestId("verify-destination")).toHaveText(/^j•••\d@example\.com$/);
  await expect(a.getByTestId("delivery-status")).toContainText("Not emailed");
  await expect(a.getByRole("note")).toContainText("EMAIL_FILE_DIR");
  await expect(a.getByRole("button", { name: /Send a new code \(in \d+ s\)/ })).toBeDisabled();
  await expect(a.getByText(/The newest code and link work until/)).toBeVisible();
  await a.getByRole("button", { name: "Show full address" }).click();
  await expect(a.getByTestId("verify-destination")).toHaveText(email);
  await a.getByText("Not in your inbox?").click();
  await expect(a.getByText(/Look in spam or junk/)).toBeVisible();
  await expectNoViolations(a, "Check your email, with its help open");

  // The link, opened in a second tab of the same browser.
  await expect.poll(() => linkTokenFor(email)).not.toBeNull();
  const token = linkTokenFor(email)!;
  const b = await a.context().newPage();
  await b.goto(`/verify-email#token=${token}`);
  await expect(b.getByText(/^j•••\d@example\.com is confirmed\. Thanks!$/)).toBeVisible();
  await expect(b).toHaveURL(/\/verify-email$/); // the token is gone from the address bar
  await expect(b.getByRole("link", { name: "Continue" })).toHaveAttribute("href", "/history");

  // The first tab moves on by itself, says why, and continues to the same page.
  await expect(a.getByRole("heading", { name: "Your email is confirmed" })).toBeVisible();
  await expect(a.getByText("You confirmed it in another tab or on another device.")).toBeVisible();
  await a.getByRole("link", { name: "Continue" }).click();
  await expect(a).toHaveURL(/\/history$/);

  // The same link again, and the link cut short by a mail app.
  await b.goto(`/verify-email#token=${token}`);
  await expect(b.getByRole("heading", { name: "This email is already confirmed" })).toBeVisible();
  await b.goto(`/verify-email#token=${token.slice(0, 20)}`);
  await expect(b.getByRole("heading", { name: "This link is incomplete" })).toBeVisible();
  // This account is confirmed already, so the way on is to continue, not to ask for a code.
  await expect(b.getByText(`Your email, ${email}, is already confirmed.`)).toBeVisible();
  await expect(b.getByRole("link", { name: "Continue" })).toBeVisible();
  await expectNoViolations(b, "a link that was cut short");
});

test("another account's link asks first, and leaves the signed-in account as it was", async ({ page: ada, browser }) => {
  const adaEmail = `ada-${Date.now()}@example.com`;
  await ada.goto("/register");
  await signUp(ada, adaEmail);
  await expect.poll(() => linkTokenFor(adaEmail)).not.toBeNull();

  const bob = await (await browser.newContext()).newPage();
  const bobEmail = `bob-${Date.now()}@example.com`;
  await bob.goto("/register");
  await signUp(bob, bobEmail);
  // Pasted into the tab that's already on "Check your email": only the #token part changes.
  await bob.goto(`/verify-email#token=${linkTokenFor(adaEmail)}`);
  await expect(bob.getByRole("heading", { name: "This link is for a different account" })).toBeVisible();
  await expectNoViolations(bob, "another account's link");
  await expect(bob.getByText(/You're signed in as/)).toContainText(bobEmail);
  await expect(bob.getByText(/You're signed in as/)).toContainText(/\(a•••\d@e•••\.com\)/);
  await bob.getByRole("button", { name: "Confirm that account's email" }).click();
  await expect(bob.getByText(/^Confirmed a•••\d@e•••\.com for the other account\.$/)).toBeVisible();
  await expect(bob.getByText(/You're still signed in as/)).toContainText(bobEmail);
  // Bob's own email still waits for its code; Ada's is confirmed, as Ada's tab sees when it looks again.
  await bob.goto("/verify-email");
  await expect(bob.getByRole("heading", { name: "Check your email" })).toBeVisible();
  await ada.reload();
  await expect(ada.getByRole("heading", { name: "Your email is confirmed" })).toBeVisible();
});
