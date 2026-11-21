import fs from "node:fs";
import path from "node:path";

import { chooseJob, expect, test } from "./fixtures";
import { E2E_OUTBOX } from "./ports";

// The e2e backend writes emails to E2E_OUTBOX (EMAIL_BACKEND=file).
function latestLinkFor(email: string): string | null {
  if (!fs.existsSync(E2E_OUTBOX)) return null;
  const mails = fs.readdirSync(E2E_OUTBOX).sort().map((f) => JSON.parse(fs.readFileSync(path.join(E2E_OUTBOX, f), "utf8")));
  const mail = mails.filter((m) => m.to === email).at(-1);
  return mail?.text.match(/https?:\/\/\S+\/reset-password#token=[\w-]+/)?.[0] ?? null;
}

test("forgot password: email link, new password, old password stops working", async ({ page }) => {
  const email = `reset-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "software-engineer");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();

  await page.goto("/login");
  await page.getByRole("link", { name: "Forgot your password?" }).click();
  // Wait for the new page: typing during the route change would land in the old page's field.
  await expect(page.getByRole("heading", { name: "Reset your password" })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByRole("status")).toContainText("If an account exists");

  await expect.poll(() => latestLinkFor(email)).not.toBeNull();
  await page.goto(latestLinkFor(email)!);
  await expect(page).toHaveURL(/\/reset-password$/); // the token was removed from the address bar
  await page.getByLabel("New password", { exact: true }).fill("BatteryStaple99");
  await page.getByLabel("Confirm new password", { exact: true }).fill("BatteryStaple99");
  await page.getByRole("button", { name: "Set new password" }).click();
  await expect(page.getByText("Your password was changed. Sign in with the new one.")).toBeVisible();

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  const main = page.locator("#main");
  await main.getByRole("button", { name: "Sign in" }).click();
  await expect(main.getByRole("alert")).toContainText(/incorrect/i);
  await page.getByLabel("Password", { exact: true }).fill("BatteryStaple99");
  await main.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
});
