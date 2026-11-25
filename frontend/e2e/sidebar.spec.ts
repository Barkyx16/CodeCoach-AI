import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";

// The sidebar narrowed to a rail of icons (Settings › Display › Sidebar, or its own button):
// real widths, keyboard and pointer labels, remembered across a reload, and checked by axe.
test("the sidebar collapses to icons and back: names on hover and focus, remembered, accessible", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/\/welcome$/);
  const sidebar = page.locator("header.header");
  const nav = page.getByRole("navigation", { name: "Main", exact: true });
  const tip = page.locator(".rail-tip");
  const full = (await sidebar.boundingBox())!.width;
  expect(full).toBeGreaterThan(240);

  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  const expand = page.getByRole("button", { name: "Expand sidebar" });
  await expect(expand).toBeFocused(); // the same button, so pressing it again undoes it
  await expect.poll(async () => (await sidebar.boundingBox())!.width).toBeLessThan(90);
  const rail = (await sidebar.boundingBox())!.width;
  // The page moves over with it: nothing sits under the rail.
  await expect.poll(async () => (await page.locator("#main").boundingBox())!.x).toBeLessThanOrEqual(rail + 1);
  // Labels are clipped, not gone: the icon links keep their names (and stay clickable).
  await expect(nav.getByRole("link", { name: "Questions", exact: true })).toBeVisible();

  // Keyboard: the name shows beside the rail; Escape dismisses it.
  await nav.getByRole("link", { name: "Lessons", exact: true }).focus();
  await expect(tip).toHaveText("Lessons");
  const tipBox = (await tip.boundingBox())!;
  expect(tipBox.x).toBeGreaterThanOrEqual(rail);
  await page.keyboard.press("Escape");
  await expect(tip).toHaveCount(0);

  // Pointer: the label shows, and stays while the pointer moves onto it (WCAG 1.4.13).
  await nav.getByRole("link", { name: "Questions", exact: true }).hover();
  await expect(tip).toHaveText("Questions");
  const over = (await tip.boundingBox())!;
  await page.mouse.move(over.x + over.width / 2, over.y + over.height / 2, { steps: 4 });
  await expect(tip).toHaveText("Questions");
  await page.mouse.move(900, 500);
  await expect(tip).toHaveCount(0);

  // A rail link goes where its name says.
  await nav.getByRole("link", { name: "Lessons", exact: true }).click();
  await expect(page).toHaveURL(/\/learn$/);

  // Every check axe makes, in both themes, with a label showing.
  for (const theme of ["light", "dark"]) {
    await setTheme(page, theme);
    await nav.getByRole("link", { name: "Questions", exact: true }).focus();
    await expect(tip).toBeVisible();
    const scan = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(scan.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`), `rail, ${theme}`).toEqual([]);
  }

  // Remembered in this browser, and applied before the app starts (no flash of the full sidebar).
  await page.goto("/learn", { waitUntil: "domcontentloaded" });
  expect(await page.evaluate(() => document.documentElement.getAttribute("data-sidebar"))).toBe("icons");
  await expect.poll(async () => (await sidebar.boundingBox())!.width).toBeLessThan(90);

  // A narrow window has no sidebar to narrow: the top bar and its menu, with every label.
  await page.setViewportSize({ width: 1000, height: 800 });
  await expect(page.getByRole("button", { name: "Expand sidebar" })).toBeHidden();
  await page.getByRole("button", { name: "Menu" }).click();
  await expect(nav.getByText("Lessons", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Menu" }).click();
  await page.setViewportSize({ width: 1440, height: 900 });

  // And back to the full sidebar from Settings.
  await page.goto("/settings");
  const sidebarChoice = page.getByRole("group", { name: "Sidebar" });
  await sidebarChoice.getByText("Full", { exact: true }).click();
  await expect(page.locator("html")).not.toHaveAttribute("data-sidebar", /.*/);
  await expect.poll(async () => (await sidebar.boundingBox())!.width).toBeGreaterThan(240);
  await expect(page.getByRole("button", { name: "Collapse sidebar" })).toBeVisible();
});
