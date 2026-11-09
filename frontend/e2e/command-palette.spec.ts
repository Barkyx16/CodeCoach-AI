import AxeBuilder from "@axe-core/playwright";

import { expect, test, type APIRequestContext, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * The command palette in a real browser (Volume 10, prompt 1), against the real API: a native modal
 * <dialog> (the page behind is inert), Ctrl+K left to the code editor inside it, a deep page's work
 * kept when the palette takes the learner elsewhere, the unsaved-work question still asked, and
 * focus returned. Synthetic accounts only.
 */
const PASSWORD = "CorrectHorse42";

async function signedIn(page: Page, request: APIRequestContext, career: string): Promise<void> {
  const email = `palette-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const r = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD, career_track: career } });
  expect(r.status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

const palette = (page: Page) => page.getByRole("dialog", { name: "Go to a page" });
const inEditor = (page: Page) => page.evaluate(() => Boolean(document.activeElement?.closest(".monaco-editor")));

test("from a problem being solved: the editor keeps Ctrl+K, the palette reaches Notes, and the code is there on return", async ({ page, request }) => {
  await signedIn(page, request, "software-engineer");
  await page.goto("/problems/two-sum");
  const editor = page.locator(".monaco-editor").first();
  await expect(editor).toBeVisible();
  await editor.click();
  await page.keyboard.press("ControlOrMeta+End");
  // One line inserted as typed text arrives (key-by-key typing into the editor can lose characters
  // to its completions).
  await page.keyboard.press("Enter");
  await page.keyboard.insertText("// my approach: one pass with a map");
  await expect(page.locator(".monaco-editor .view-lines").first()).toContainText("my approach: one pass with a map");
  // Inside the editor, Ctrl+K starts the editor's own two-key shortcuts: no palette.
  await page.keyboard.press("Control+K");
  await page.keyboard.press("Escape");
  await expect(palette(page)).toHaveCount(0);
  expect(await inEditor(page)).toBe(true);

  // Anywhere else on the page it opens, as a real modal dialog with the field focused.
  const heading = page.getByRole("heading", { level: 1 });
  await heading.click();
  await page.keyboard.press("Control+K");
  await expect(palette(page)).toBeVisible();
  expect(await page.evaluate(() => document.querySelector("dialog.palette")?.matches(":modal"))).toBe(true);
  await expect(page.getByRole("combobox", { name: "Go to a page" })).toBeFocused();
  // The page behind can't be clicked or tabbed into while it's open.
  for (let i = 0; i < 6; i++) await page.keyboard.press("Tab");
  expect(await page.evaluate(() => document.querySelector("dialog.palette")?.contains(document.activeElement) || document.activeElement === document.body)).toBe(true);

  await page.getByRole("combobox", { name: "Go to a page" }).fill("notes");
  await expect(palette(page).getByRole("option")).toHaveText([/^Notes/]);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/notes$/);
  await expect(page.getByRole("heading", { name: "Your notes", level: 1 })).toBeVisible();
  await expect(page.locator("#main")).toBeFocused();

  await page.goBack();
  await expect(page).toHaveURL(/\/problems\/two-sum$/);
  await expect(page.locator(".monaco-editor .view-lines").first()).toContainText("my approach: one pass with a map");
});

test("unsaved goals: the palette's choice is asked about, staying keeps the typing, and focus goes back to the field", async ({ page, request }) => {
  await signedIn(page, request, "registered-nurse");
  await page.goto("/plan/goals");
  const specialty = page.getByLabel(/Specialty or focus/);
  await specialty.fill("Emergency");
  let asked = "";
  page.once("dialog", (d) => { asked = d.message(); void d.dismiss(); });
  await page.keyboard.press("Control+K");
  await page.getByRole("combobox", { name: "Go to a page" }).fill("notes");
  await page.keyboard.press("Enter");
  await expect.poll(() => asked).toMatch(/^Your changes to your goals aren't saved/);
  await expect(page).toHaveURL(/\/plan\/goals$/);
  await expect(specialty).toHaveValue("Emergency");
  await expect(specialty).toBeFocused();
  // Escape closes it the same way, back to the same field.
  await page.keyboard.press("Control+K");
  await expect(palette(page)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(palette(page)).toHaveCount(0);
  await expect(specialty).toBeFocused();
});

test("the open palette has no accessibility violations, in the dark and the light theme", async ({ page, request }) => {
  await signedIn(page, request, "registered-nurse");
  await page.goto("/dashboard");
  for (const theme of ["dark", "light"]) {
    await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
    await page.getByRole("button", { name: "Go to…" }).click();
    await expect(palette(page)).toBeVisible();
    await page.getByRole("combobox", { name: "Go to a page" }).fill("st");
    const results = await new AxeBuilder({ page }).include("dialog.palette").analyze();
    expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(", ")}`), theme).toEqual([]);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "Go to…" })).toBeFocused();
  }
});
