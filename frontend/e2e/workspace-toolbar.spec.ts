import { expect, test, type Page } from "./fixtures";

// The coding workspace's editor toolbar when its buttons don't fit on one line (a narrow centre
// panel, larger text, or a window narrowed after the editor loaded): every button must stay visible
// and clickable, never slide under the code editor. Chromium, desktop layout (wider than 900px);
// emulated viewports and the app's own text-size setting, not a physical device or browser zoom.

const DISPLAY_KEY = "codecoach.display.v1";

async function openTwoSum(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await page.getByRole("button", { name: "Start this problem" }).click();
  await expect(page).toHaveURL(/\/problems\/two-sum$/);
  await expect(page.locator(".editor-toolbar")).toBeVisible();
}

/** Whether the toolbar wrapped, and, for each button in it, whether a pointer at its centre lands on it. */
async function toolbar(page: Page) {
  return page.evaluate(() => {
    const bar = document.querySelector(".editor-toolbar") as HTMLElement;
    const lang = bar.querySelector(".editor-toolbar__lang") as HTMLElement;
    const buttons = [...bar.querySelectorAll("button")] as HTMLElement[];
    const wrapped = buttons.some((b) => b.getBoundingClientRect().top >= lang.getBoundingClientRect().bottom - 1)
      || new Set(buttons.map((b) => Math.round(b.getBoundingClientRect().top))).size > 1;
    const hits = buttons.map((b) => {
      const r = b.getBoundingClientRect();
      const at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return { name: b.getAttribute("aria-label") ?? b.textContent?.trim() ?? "", reachable: !!at && b.contains(at) };
    });
    return { wrapped, hits };
  });
}

async function expectUsable(page: Page, where: string) {
  await page.locator(".editor-toolbar").scrollIntoViewIfNeeded();
  const state = await toolbar(page);
  expect(state.wrapped, `${where}: the toolbar wraps (otherwise this case tests nothing)`).toBe(true);
  for (const hit of state.hits) expect(hit.reachable, `${where}: “${hit.name}” is under the pointer at its centre`).toBe(true);
}

test("toolbar buttons stay visible and clickable when they wrap: narrow panel, larger text, resize after load", async ({ page }) => {
  // A narrow centre panel: desktop layout just above the 900px breakpoint.
  await page.setViewportSize({ width: 960, height: 640 });
  await openTwoSum(page);
  await expectUsable(page, "960px window");

  // Narrowed after the editor initialised.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.reload();
  await expect(page.locator(".editor-toolbar")).toBeVisible();
  await page.setViewportSize({ width: 940, height: 640 });
  await expectUsable(page, "1440px window narrowed to 940px");

  // Larger text (the app's display setting) in a 1280px window.
  await page.evaluate((key) => localStorage.setItem(key, JSON.stringify({ text: "larger" })), DISPLAY_KEY);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-text", "larger");
  await expectUsable(page, "1280px window, larger text");

  // A real click (no force) on the primary action after wrapping.
  await page.getByRole("button", { name: /^(Submit|Save attempt)$/ }).click({ timeout: 10_000 });
  await expect(page.getByText(/Saved, but not run yet|All tests passed|didn't pass|Failed/i).first()).toBeVisible({ timeout: 60_000 });
  // Reset keeps its name and scope (it's disabled until the code changes, but it's there and reachable).
  await expect(page.getByRole("button", { name: "Reset code" })).toBeVisible();
});
