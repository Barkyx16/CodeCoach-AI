import { expect, test } from "@playwright/test";

test("mobile workspace uses tabs instead of side-by-side panels", async ({ page }) => {
  await page.goto("/problems/two-sum");
  await expect(page.getByRole("heading", { name: "Two Sum", level: 1 })).toBeVisible();
  const tabs = page.getByRole("tablist", { name: "Workspace" });
  await expect(tabs).toBeVisible();
  await tabs.getByRole("tab", { name: "Code" }).click();
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await tabs.getByRole("tab", { name: "Coach" }).click();
  await expect(page.getByRole("button", { name: /sign in or continue as guest/i })).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/05-mobile-workspace.png" });
});
