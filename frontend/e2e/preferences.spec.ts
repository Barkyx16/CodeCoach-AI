import { expect, test } from "@playwright/test";

test("editor preferences survive reload and navigating away saves the latest keystrokes", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await page.getByRole("button", { name: "Start this problem" }).click(); // the optional welcome
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollHeight <= innerHeight + 1)).toBe(true);
  await expect.poll(() => page.getByRole("region", { name: "Problem description" }).evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true);
  await page.getByRole("button", { name: "Editor settings", exact: true }).click();
  await page.getByLabel("Font size", { exact: true }).selectOption("18");
  await page.getByLabel("Wrap long lines").check();
  await expect(page.locator(".monaco-editor .view-lines")).toHaveCSS("font-size", "18px");
  await page.locator(".monaco-editor").click();
  await page.keyboard.press("ControlOrMeta+End");
  await page.keyboard.insertText("\n// preserve my latest edit");
  // Do not wait for the debounce: route cleanup must flush the last edit.
  await page.getByRole("link", { name: "Dashboard", exact: true }).click();
  await expect(page.getByRole("region", { name: "Summary" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("region", { name: "Summary" })).toBeVisible();
  await page.goto("/problems/two-sum");
  await expect(page.locator(".monaco-editor .view-lines")).toContainText("preserve my latest edit");
  await page.reload();
  await expect(page.locator(".monaco-editor .view-lines")).toHaveCSS("font-size", "18px");
  await expect(page.locator(".monaco-editor .view-lines")).toContainText("preserve my latest edit");
  await page.getByRole("link", { name: "Analytics", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Analytics", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Practice statistics" })).toBeVisible();
  await expect(page.getByText("Activity over time", { exact: true })).toBeVisible();
});
