import { expect, test } from "@playwright/test";

// Real-browser checks of the cookie-backed session: the parts jsdom can't prove.
test("the session survives reloads via an HttpOnly cookie that page scripts can't read", async ({ page, context }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/two-sum/);

  const cookie = (await context.cookies()).find((c) => c.name === "cc_refresh");
  expect(cookie).toBeDefined();
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
  expect(cookie?.path).toBe("/api/v1/auth");
  // Invisible to JavaScript, and no access token anywhere in browser storage.
  expect(await page.evaluate(() => document.cookie)).not.toContain("cc_refresh");
  const stored = await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }));
  expect(stored).not.toMatch(/eyJ[\w-]+\.[\w-]+\.[\w-]+/); // no JWT

  // A reload of a protected page restores the session from the cookie.
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { level: 1, name: /progress/i })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: /progress/i })).toBeVisible();
  await expect(page).toHaveURL(/\/dashboard$/);

  // Signing out clears the cookie, so a reload no longer has a session.
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/$/);
  expect((await context.cookies()).find((c) => c.name === "cc_refresh")).toBeUndefined();
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
});

test("a guest keeps their work by upgrading to a full account", async ({ page }) => {
  const email = `upgrade-${Date.now()}@example.com`;
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/two-sum/);
  await page.getByRole("button", { name: "Get a hint" }).click(); // some guest activity to keep
  await expect(page.getByText(/level 1/i).first()).toBeVisible();

  await page.goto("/settings");
  const card = page.getByRole("form", { name: "Keep your progress" });
  await expect(card.getByText(/deleted after \d+ days without activity/)).toBeVisible();
  await card.getByLabel("Email").fill(email);
  await card.getByLabel("Password").fill("CorrectHorse42");
  await card.getByRole("button", { name: "Create my account" }).click();
  await expect(page.getByText(/Your account is ready/)).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await page.goto("/history");
  await page.getByRole("tab", { name: "AI feedback" }).click();
  await expect(page.getByText("Hint level 1").first()).toBeVisible(); // the guest's hint survived
});
