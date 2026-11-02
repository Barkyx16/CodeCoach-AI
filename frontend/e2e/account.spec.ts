import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const OUTBOX = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../backend/e2e-outbox");

function latestCodeFor(email: string): string | null {
  if (!fs.existsSync(OUTBOX)) return null;
  const mails = fs.readdirSync(OUTBOX).sort().map((f) => JSON.parse(fs.readFileSync(path.join(OUTBOX, f), "utf8")));
  return mails.filter((m) => m.to === email).at(-1)?.text.match(/verification code is: (\d{6})/)?.[1] ?? null;
}

test("sign up, verify with the emailed code, change email, sign out", async ({ page }) => {
  const email = `verify-${Date.now()}@example.com`;
  const main = page.locator("#main");
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  const password = page.getByLabel("Password", { exact: true });
  await password.fill("CorrectHorse42");
  // The eye button reveals what was typed.
  await page.getByRole("button", { name: "Show password" }).click();
  await expect(password).toHaveAttribute("type", "text");
  await expect(page.getByText("At least 10 characters")).toBeVisible();
  await page.getByLabel("Job you're preparing for").selectOption("software-engineer");
  await main.getByRole("button", { name: "Create account" }).click();

  // Straight to "Check your email", with the real code from the real email.
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
  await expect.poll(() => latestCodeFor(email)).not.toBeNull();
  await page.getByLabel("Verification code").fill(latestCodeFor(email)!);
  await page.getByRole("button", { name: "Verify email" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto("/settings");
  const emailCard = page.getByRole("form", { name: "Email" });
  await expect(emailCard.getByText("Verified", { exact: true })).toBeVisible();

  // Change the email: needs the password, and the new address must be verified again.
  const newEmail = `changed-${Date.now()}@example.com`;
  await emailCard.getByLabel("New email").fill(newEmail);
  await emailCard.getByLabel("Current password", { exact: true }).fill("CorrectHorse42");
  await emailCard.getByRole("button", { name: "Change email" }).click();
  await expect(emailCard.getByText("Not verified")).toBeVisible();
  await expect(emailCard.getByText(newEmail)).toBeVisible();
  await emailCard.getByRole("link", { name: "Enter the verification code" }).click();
  await expect.poll(() => latestCodeFor(newEmail)).not.toBeNull();
  await page.getByLabel("Verification code").fill(latestCodeFor(newEmail)!);
  await page.getByRole("button", { name: "Verify email" }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByRole("form", { name: "Email" }).getByText("Verified", { exact: true })).toBeVisible();

  // Sign out of this device from Settings; signing in uses the new email.
  await page.getByRole("region", { name: "Sign out" }).getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/login");
  await page.getByLabel("Email").fill(newEmail);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await main.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
});
