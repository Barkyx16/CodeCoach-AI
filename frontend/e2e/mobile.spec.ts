import { expect, test } from "@playwright/test";

test("signed-in navigation fits narrow screens and keeps account settings accessible", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await page.getByRole("button", { name: "Start this problem" }).click(); // the optional welcome
  await expect(page).toHaveURL(/two-sum/);
  for (const width of [320, 375, 390, 768]) {
    await page.setViewportSize({ width, height: 812 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole("button", { name: "Menu" }).click();
    await expect(page.getByRole("link", { name: "Dashboard", exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "Menu" })).toBeFocused();
  }
  await page.getByRole("button", { name: "Menu" }).click();
  await page.getByRole("link", { name: "Guest, account settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
  for (const width of [320, 375, 390, 768]) {
    await page.setViewportSize({ width, height: 812 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await expect(page.getByRole("button", { name: "Menu" })).toHaveAttribute("aria-expanded", "false");
  expect(errors).toEqual([]);
});

test("mobile workspace uses tabs instead of side-by-side panels", async ({ page }) => {
  await page.goto("/problems/two-sum");
  await expect(page.getByRole("heading", { name: "Two Sum", level: 1 })).toBeVisible();
  const tabs = page.getByRole("tablist", { name: "Workspace" });
  await expect(tabs).toBeVisible();
  await tabs.getByRole("tab", { name: "Problem" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(tabs.getByRole("tab", { name: "Code" })).toBeFocused();
  await expect(page.getByRole("tabpanel", { name: "Code", exact: true })).toBeVisible();
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await page.keyboard.press("End");
  await expect(tabs.getByRole("tab", { name: "Coach" })).toBeFocused();
  await expect(page.getByRole("button", { name: /sign in or continue as guest/i })).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/05-mobile-workspace.png" });
});

test("a question round fits a 320px screen and keeps every control reachable", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await page.getByRole("button", { name: "Start this problem" }).click(); // the optional welcome
  await expect(page).toHaveURL(/two-sum/);
  await page.goto("/interviews/questions");
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page.getByText(/QUESTION 1 OF 5/)).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  for (const name of ["Skip", "Next question", "Hide"]) {
    const control = page.getByRole("button", { name, exact: true });
    await control.scrollIntoViewIfNeeded();
    await expect(control).toBeVisible();
    const box = await control.boundingBox();
    expect(box && box.height >= 32 && box.x >= 0 && box.x + box.width <= 320, `${name} fits and is touch-sized`).toBe(true);
  }
  page.on("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: "End early" }).click();
  await expect(page.getByText(/ENDED EARLY/)).toBeVisible();
});
