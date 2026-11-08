import AxeBuilder from "@axe-core/playwright";
import { readFile } from "node:fs/promises";

import { expect, test, type Page } from "./fixtures";

/**
 * A support report in a real browser (Volume 7, prompt 8), against the real API. A hint whose
 * connection drops opens "Get help with this" in place: the code stays in the editor, the
 * report says no reply came back (no reference made up), Copy puts exactly the preview on the
 * clipboard, and the downloaded file is the preview byte for byte. Synthetic secrets put in the
 * page's URL, the editor and browser storage never appear in it. No WCAG A/AA violations with
 * the report open.
 */
const SECRET = "sk-SYNTHETIC-canary-0123456789abcdef";

async function startAsGuest(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/\/welcome$/);
}

test("a dropped hint: the report in place, copied and downloaded exactly as previewed", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await startAsGuest(page);
  await page.evaluate((secret) => localStorage.setItem("codecoach.e2e.canary", secret), SECRET);
  await page.goto(`/problems/two-sum?utm=${SECRET}`);
  await expect(page.getByRole("heading", { name: "Two Sum", level: 1 })).toBeVisible();
  const editor = page.getByTestId("code-editor");
  await expect(editor).toContainText("write your solution here");

  await page.route("**/api/v1/ai/hint", (route) => route.abort("connectionreset"));
  const coach = page.getByRole("region", { name: "AI coach" });
  await coach.getByRole("button", { name: "Get a hint" }).click();
  await expect(page.getByText("The hint didn't go through.")).toBeVisible();
  await page.getByRole("button", { name: "Get help with this" }).click();

  const region = page.getByRole("region", { name: "Support report" });
  const preview = region.getByRole("textbox", { name: "The report" });
  await expect(preview).toBeVisible();
  await region.getByLabel(/What happened\?/).fill("The hint button spun, then said it didn't go through.");
  await expect.poll(async () => JSON.parse(await preview.inputValue()).server_said).not.toBe("not answered yet");
  const text = await preview.inputValue();
  const report = JSON.parse(text);
  expect(report.format).toBe("codecoach-support-report");
  expect(report.page).toEqual({ name: "Coding workspace", path: "/problems/two-sum" });
  expect(report.session).toBe("guest");
  expect(report.problem).toMatchObject({ action: "The hint", category: "offline", code: "network_error", status: 0, request_id: null });
  expect(report.recent_failed_requests).toContainEqual(expect.objectContaining({ method: "POST", path: "/api/v1/ai/hint", status: 0 }));
  expect(report.description).toBe("The hint button spun, then said it didn't go through.");
  expect(text).not.toContain(SECRET);
  expect(text).not.toContain("write your solution here");
  await expect(editor).toContainText("write your solution here"); // the work is where it was

  await region.getByRole("button", { name: "Copy the report" }).click();
  await expect(region.getByRole("status")).toContainText("Copied the report.");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(text);

  const download = page.waitForEvent("download");
  await region.getByRole("button", { name: /^Download codecoach-support-report-\d{8}-\d{4}\.json$/ }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^codecoach-support-report-\d{8}-\d{4}\.json$/);
  expect(await readFile((await file.path())!, "utf8")).toBe(text);

  const results = await new AxeBuilder({ page }).include(".action-error").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);
});

test("the report page works with keyboard alone, signed out", async ({ page }) => {
  await page.goto("/help");
  await page.getByRole("link", { name: "Get a support report" }).click();
  await expect(page.getByRole("heading", { name: "Support report", level: 1 })).toBeVisible();
  const description = page.getByLabel(/What happened\?/);
  await description.focus();
  await page.keyboard.type("<b>not bold</b>");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("textbox", { name: "The report" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Copy the report" })).toBeFocused();
  const report = JSON.parse(await page.getByRole("textbox", { name: "The report" }).inputValue());
  expect(report.session).toBe("signed_out");
  expect(report.recent_failed_requests).toEqual([]); // the refused session check on load isn't a failure
  expect(report.page).toEqual({ name: "Help", path: "/help" });
  expect(report.description).toBe("<b>not bold</b>");
  await expect(page.locator("main b", { hasText: "not bold" })).toHaveCount(0);
  // Fits the screen, a phone's too: the report scrolls inside its box, never the page sideways.
  for (const width of [1440, 360]) {
    await page.setViewportSize({ width, height: 800 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), `at ${width}px`).toBeLessThanOrEqual(0);
  }
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);
});
