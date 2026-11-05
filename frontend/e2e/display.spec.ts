import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "./fixtures";

// Accessibility and comfort checks in a real browser: keyboard-only journeys, display preferences
// (themes, higher contrast, text size, reduced motion), reflow at 320px, focus mode, the code
// editor's keyboard exit and unavailable storage. Automated checks; see docs/ACCESSIBILITY.md for
// what was checked by hand and what wasn't.

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const DISPLAY_KEY = "codecoach.display.v1";

/** Press Tab (or Shift+Tab) until `target` has focus: proves it's reachable by keyboard alone. */
async function tabTo(page: Page, target: Locator, { max = 80, back = false } = {}) {
  await expect(target, "tabTo needs exactly one target").toHaveCount(1);
  for (let i = 0; i < max; i++) {
    if (await target.evaluate((el) => el === document.activeElement).catch(() => false)) return;
    await page.keyboard.press(back ? "Shift+Tab" : "Tab");
  }
  throw new Error(`Not reachable with ${back ? "Shift+Tab" : "Tab"} in ${max} presses: ${target}`);
}

/** The focused element shows a visible focus indicator (ring or outline). */
async function expectFocusIndicator(target: Locator) {
  const style = await target.evaluate((el) => {
    const s = getComputedStyle(el);
    return { shadow: s.boxShadow, outline: s.outlineStyle, width: s.outlineWidth };
  });
  expect(style.shadow !== "none" || (style.outline !== "none" && style.width !== "0px"), `focus indicator on ${target}`).toBe(true);
}

async function startGuestByKeyboard(page: Page) {
  await page.goto("/");
  await tabTo(page, page.getByRole("button", { name: /try it now/i }));
  await page.keyboard.press("Enter");
  // The optional welcome, by keyboard too.
  await expect(page).toHaveURL(/\/welcome$/);
  await tabTo(page, page.getByRole("button", { name: "Start this problem" }));
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/two-sum/);
  await expect(page.getByRole("heading", { name: "Two Sum", level: 1 })).toBeVisible();
}

async function noHorizontalScroll(page: Page, where: string) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), { message: `no sideways scrolling on ${where}` }).toBe(true);
}

async function axe(page: Page, where: string) {
  await expect(page.locator(".spinner")).toHaveCount(0, { timeout: 15_000 });
  const results = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 4).map((n) => n.target.join(" ")) })), `axe on ${where}`).toEqual([]);
}

test("keyboard only: find a question with a filter, answer it, recover from an error, use focus mode, go back to the list", async ({ page }) => {
  await startGuestByKeyboard(page);
  await page.goto("/problems?view=questions&kind=behavioral");
  await expect(page.getByRole("button", { name: /Remove Format/ })).toBeVisible();

  // Tabs: arrow keys move between levels, as in any tab list.
  const easy = page.getByRole("tab", { name: /^Easy/ });
  await tabTo(page, easy);
  await expectFocusIndicator(easy);
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /^Medium/ })).toBeFocused();
  await expect(page.getByRole("tab", { name: /^Medium/ })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("ArrowLeft");
  await expect(easy).toHaveAttribute("aria-selected", "true");

  const first = page.locator(".problem-row").first();
  const title = (await first.locator(".problem-row__title").innerText()).replace(/^\d+/, "").trim();
  await tabTo(page, first);
  await expectFocusIndicator(first);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: title, level: 1 })).toBeVisible();

  const box = page.getByRole("textbox", { name: "Your answer" });
  await tabTo(page, box);
  const answer = "In my last project our build broke the night before a release. I owned the fix: I bisected the commits, found the bad dependency bump, pinned it and wrote a check so it can't happen again. We shipped on time.";
  await page.keyboard.type(answer);

  // A failed request: the error is announced, tied to the answer box, and the draft is kept.
  await page.route("**/api/v1/careers/*/questions/*/answers**", (route) => route.abort(), { times: 1 });
  const submit = page.getByRole("button", { name: "Get feedback" });
  await tabTo(page, submit);
  await page.keyboard.press("Enter");
  const error = page.locator("#answer-error");
  await expect(error).toHaveAttribute("role", "alert");
  await expect(box).toHaveAttribute("aria-describedby", /answer-error/);
  await expect(box).toHaveValue(answer);
  await expect(submit, "focus stays on the button after the request ends").toBeFocused();

  // Try again from the same place.
  await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Feedback", exact: true })).toBeVisible();
  await expect(error).toHaveCount(0);

  // Focus mode by keyboard: on, essentials still there, Escape returns focus to the toggle.
  const toggle = page.getByRole("button", { name: "Focus mode", exact: true });
  await tabTo(page, toggle, { back: true });
  await page.keyboard.press("Space");
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Get feedback" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
  await expect(toggle).toBeFocused();

  // Back to the filtered list it came from, filters intact.
  const back = page.getByRole("link", { name: /^Back to/ });
  await tabTo(page, back, { back: true });
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/view=questions&kind=behavioral/);
  await expect(page.getByRole("button", { name: /Remove Format/ })).toBeVisible();
});

test("keyboard only: a mock interview round, including focus mode and ending early", async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
  await startGuestByKeyboard(page);
  await page.goto("/interviews/questions");
  await tabTo(page, page.getByRole("button", { name: "Start interview" }));
  await page.keyboard.press("Enter");
  await expect(page.getByText(/QUESTION 1 OF 5/)).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused(); // a new question takes focus

  await tabTo(page, page.getByRole("textbox", { name: "Your answer" }));
  await page.keyboard.type("I want this job because I like building things people use every day, and I learn fastest by shipping.");
  await page.keyboard.press("Control+Enter");
  await expect(page.getByText(/QUESTION 2 OF 5/)).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();

  const toggle = page.getByRole("button", { name: "Focus mode", exact: true });
  await tabTo(page, toggle);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
  // Never hidden: the deadline, recording status and the way out.
  await expect(page.getByRole("timer")).toBeVisible();
  await expect(page.locator(".voice-status")).toBeVisible();
  await expect(page.getByRole("button", { name: "End early" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Exit focus mode" })).toBeVisible();

  await tabTo(page, page.getByRole("button", { name: "End early" }));
  await page.keyboard.press("Enter");
  await expect(page.getByText(/ENDED EARLY/)).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible(); // a new page: focus mode ended
});

test("the code editor has a documented keyboard exit, and disclosures work from the keyboard", async ({ page }) => {
  await page.goto("/problems/two-sum");
  await expect(page.locator(".monaco-editor")).toBeVisible();
  const inEditor = () => page.evaluate(() => Boolean(document.activeElement?.closest(".monaco-editor")));

  const settings = page.getByRole("button", { name: "Editor settings" });
  await tabTo(page, settings);
  await page.keyboard.press("Enter");
  await expect(settings).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("Enter");
  await expect(settings).toHaveAttribute("aria-expanded", "false");

  await tabTo(page, page.getByRole("textbox", { name: /^Java code editor/ }));
  await expect(page.locator(".code-editor__hint")).toContainText("Ctrl");
  await page.keyboard.press("Tab");
  expect(await inEditor(), "Tab indents while in the editor").toBe(true);
  await page.keyboard.press("Control+M"); // Monaco: "Tab moves focus"
  await expect(page.locator(".code-editor__hint")).toContainText("Tab moves focus out of the editor");
  await page.keyboard.press("Tab");
  expect(await inEditor(), "after Ctrl+M, Tab leaves the editor").toBe(false);
  await expect(page.locator(".code-editor__hint")).toHaveCount(0);
  // Back in with Shift+Tab, Ctrl+M again restores indenting.
  await page.keyboard.press("Shift+Tab");
  expect(await inEditor()).toBe(true);
  await page.keyboard.press("Control+M");
  await expect(page.locator(".code-editor__hint")).toContainText("Tab indents");
});

test("display settings: chosen by keyboard, applied before the page renders, readable in every theme", async ({ page }) => {
  await startGuestByKeyboard(page);
  await page.goto("/settings");
  const theme = page.getByRole("group", { name: "Theme" });
  await tabTo(page, theme.getByRole("radio", { name: "Match device" }));
  await page.keyboard.press("ArrowRight");
  await expect(theme.getByRole("radio", { name: "Light" })).toBeChecked();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.keyboard.press("Tab");
  await page.keyboard.press("ArrowRight"); // Contrast: Higher
  await expect(page.locator("html")).toHaveAttribute("data-contrast", "high");
  await expect(page.getByRole("status").getByText("Saved in this browser.", { exact: true })).toBeVisible();

  // Applied by /display-init.js before React starts, so there's no flash of the other theme.
  await page.goto("/problems", { waitUntil: "commit" });
  await page.waitForFunction(() => document.readyState !== "loading");
  expect(await page.evaluate(() => [document.documentElement.dataset.theme, document.documentElement.dataset.contrast])).toEqual(["light", "high"]);

  for (const prefs of [{ theme: "light" }, { theme: "light", contrast: "high" }, { theme: "dark", contrast: "high" }]) {
    await page.evaluate(([key, value]) => localStorage.setItem(key!, value!), [DISPLAY_KEY, JSON.stringify(prefs)]);
    for (const path of ["/", "/problems?view=questions&career=registered-nurse", "/careers/registered-nurse/questions/m-walk-0", "/learn/se-sliding-window", "/settings", "/dashboard"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      await axe(page, `${path} with ${JSON.stringify(prefs)}`);
    }
  }
});

test("largest text at 320px and at 200% zoom: content reflows without sideways scrolling", async ({ page }) => {
  // A sweep of 20+ page loads plus a live round: well over a minute on a slow CI runner.
  test.setTimeout(150_000);
  page.on("dialog", (d) => void d.accept());
  await page.addInitScript(([key]) => {
    if (!sessionStorage.getItem("seeded")) {
      localStorage.setItem(key!, JSON.stringify({ text: "larger", spacing: "spacious" }));
      sessionStorage.setItem("seeded", "1");
    }
  }, [DISPLAY_KEY]);
  await page.setViewportSize({ width: 320, height: 640 });
  await startGuestByKeyboard(page);
  await expect(page.locator("html")).toHaveAttribute("data-text", "larger");
  // Text really is larger (rem-based sizes follow the root size).
  expect(await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize))).toBe(20);
  for (const width of [320, 640]) { // 640px ≈ a 1280px window at 200% zoom
    await page.setViewportSize({ width, height: 640 });
    for (const path of ["/", "/problems", "/problems?view=questions&career=registered-nurse", "/careers/registered-nurse/questions/m-walk-0",
      "/learn/se-sliding-window", "/history", "/settings", "/notes/new", "/interviews/questions", "/problems/two-sum"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      await noHorizontalScroll(page, `${path} at ${width}px`);
    }
    await page.goto("/careers/registered-nurse/questions/m-walk-0");
    await page.getByRole("button", { name: "Focus mode", exact: true }).click();
    await noHorizontalScroll(page, `focus mode at ${width}px`);
    await expect(page.getByRole("button", { name: "Exit focus mode" }).first()).toBeInViewport();
  }
  await page.goto("/interviews/questions");
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page.getByText(/QUESTION 1 OF 5/)).toBeVisible();
  await noHorizontalScroll(page, "live interview round");
  await page.getByRole("button", { name: "End early" }).click();
  await expect(page.getByText(/ENDED EARLY/)).toBeVisible();
});

test("reduced motion: the device setting and the app setting both turn off transitions", async ({ page }) => {
  const duration = () => page.getByRole("button", { name: /try it now/i }).evaluate((el) => getComputedStyle(el).transitionDuration);
  await page.goto("/");
  expect(await duration()).not.toMatch(/^0s|^1e-05s/); // normally animated
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(parseFloat(await duration())).toBeLessThan(0.001);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.evaluate(([key]) => localStorage.setItem(key!, JSON.stringify({ motion: "reduce" })), [DISPLAY_KEY]);
  await page.reload();
  expect(parseFloat(await duration())).toBeLessThan(0.001);
});

test("blocked storage: the app still works, and Settings says preferences won't be kept", async ({ page }) => {
  // As in a browser that blocks site data: touching localStorage/sessionStorage throws.
  await page.addInitScript(() => {
    for (const name of ["localStorage", "sessionStorage"]) {
      Object.defineProperty(window, name, { configurable: true, get() { throw new DOMException("The operation is insecure.", "SecurityError"); } });
    }
  });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await startGuestByKeyboard(page);
  await page.goto("/settings");
  const status = page.getByRole("status").filter({ hasText: "won't store settings" });
  await expect(status).toBeVisible();
  await page.getByRole("group", { name: "Text size" }).getByText("Larger").click();
  await expect(page.locator("html")).toHaveAttribute("data-text", "larger"); // still applies for this visit
  await page.goto("/careers/registered-nurse/questions/m-walk-0");
  await page.getByRole("textbox", { name: "Your answer" }).fill("Typing works without storage.");
  await expect(page.getByRole("textbox", { name: "Your answer" })).toHaveValue("Typing works without storage.");
  expect(errors).toEqual([]);
});

test("forced colors (Windows High Contrast): the focus indicator is still drawn", async ({ page }) => {
  await page.emulateMedia({ forcedColors: "active" });
  await page.goto("/");
  const target = page.getByRole("button", { name: /try it now/i });
  await tabTo(page, target);
  const style = await target.evaluate((el) => { const s = getComputedStyle(el); return { style: s.outlineStyle, width: s.outlineWidth, color: s.outlineColor }; });
  // Box-shadow rings are dropped in this mode; the outline takes a system colour instead of transparent.
  expect(style.style).toBe("solid");
  expect(style.width).toBe("2px");
  expect(style.color).not.toMatch(/rgba\(0, 0, 0, 0\)|transparent/);
});
