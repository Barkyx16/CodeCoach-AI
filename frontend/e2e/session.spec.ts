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
