import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * What the coach will read (Volume 12, prompt 2) against the real API and the built-in coach: a
 * code review shows exactly what it would send (a secret-looking string already replaced), costs
 * nothing until it's sent, can be cancelled, refuses code changed after checking until checked
 * again, and then sends. Axe in both themes on the preview. Synthetic data only.
 */
const WORD = ["pass", "word"].join(""); // built at run time so no file holds a credential-shaped line
const CODE = `class Solution {
    public int[] twoSum(int[] nums, int target) {
        String ${WORD} = "synthetic-only-1";
        for (int i = 0; i < nums.length; i++) {
            for (int j = i + 1; j < nums.length; j++) {
                if (nums[i] + nums[j] == target) return new int[] {i, j};
            }
        }
        return new int[0];
    }
}`;

async function replaceEditorContent(page: Page, code: string) {
  await page.locator(".monaco-editor").first().click();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.press("Delete");
  await page.evaluate((text) => navigator.clipboard.writeText(text), code);
  await page.keyboard.press("ControlOrMeta+V");
}

test("a code review shows what the coach will read, and sends only that", async ({ page, context, request }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const email = `cc-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "software-engineer" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const used = async () => ((await (await request.get(`${API_URL}/api/v1/ai/usage`, { headers: auth })).json()) as { used_today: number }).used_today;

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.goto("/problems/two-sum");
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await replaceEditorContent(page, CODE);
  await page.getByRole("tab", { name: "Code review" }).click();
  const before = await used();

  // Check: exactly what would be sent, with the secret-looking string already replaced.
  await page.getByRole("button", { name: "Review my code" }).click();
  const panel = page.locator("section").filter({ has: page.getByRole("heading", { name: "What the coach will read" }) });
  await expect(panel.getByText(/The built-in coach, on CodeCoach's own server: nothing leaves it/)).toBeVisible();
  const sent = panel.getByLabel("Exactly what's sent: Your code");
  await expect(sent).toContainText(`${WORD} = "[REDACTED]"`);
  await expect(sent).not.toContainText("synthetic-only-1");
  await expect(panel.getByText("1 secret-looking string replaced with [REDACTED].")).toBeVisible();
  await expect(panel.getByText("Worked out by CodeCoach")).toBeVisible();
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".coach-context").analyze();
    expect(scan.violations.map((v) => v.id), `preview, ${theme}`).toEqual([]);
  }

  // Cancel: nothing sent, nothing spent.
  await panel.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText("Cancelled. Nothing was sent.")).toBeVisible();
  expect(await used()).toBe(before);

  // Check again, then change the code: it can't be sent until it's checked again.
  await page.getByRole("button", { name: "Review my code" }).click();
  await expect(panel.getByLabel("Exactly what's sent: Your code")).toBeVisible();
  await page.locator(".monaco-editor").first().click();
  await page.keyboard.press("ControlOrMeta+End");
  // Inserted as typed text arrives: key by key, the editor's completions can take characters (CI
  // run 311 got "// checkeain").
  await page.keyboard.press("Enter");
  await page.keyboard.insertText("// checked again");
  await expect(panel.getByText(/Your code changed since this was checked/)).toBeVisible();
  await expect(panel.getByRole("button", { name: "Send for review" })).toBeDisabled();
  expect(await used()).toBe(before);
  await panel.getByRole("button", { name: "Check again" }).click();
  await expect(panel.getByLabel("Exactly what's sent: Your code")).toContainText("// checked again");
  await panel.getByRole("button", { name: "Send for review" }).click();
  await expect(page.getByText("What's working")).toBeVisible();
  expect(await used()).toBe(before + 1);
});

test("a hint shows what the coach will read for its level, costs nothing to check, and sends only that", async ({ page, context, request }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const email = `cch-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "software-engineer" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const used = async () => ((await (await request.get(`${API_URL}/api/v1/ai/usage`, { headers: auth })).json()) as { used_today: number }).used_today;

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.goto("/problems/two-sum");
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await replaceEditorContent(page, CODE);
  const coach = page.getByRole("region", { name: "AI coach" });
  const before = await used();

  await coach.getByRole("button", { name: "Get a hint" }).click();
  const panel = coach.locator("section").filter({ has: page.getByRole("heading", { name: "What the coach will read" }) });
  await expect(panel.getByText("Level 1 of 4: Nudge.")).toBeVisible();
  await expect(panel.getByText("Your first hint for this problem.")).toBeVisible();
  await expect(panel.getByLabel("Exactly what's sent: The hint level you're asking for")).toHaveText("Requested hint level: 1 (nudge).");
  const sent = panel.getByLabel("Exactly what's sent: Your code");
  await expect(sent).toContainText(`${WORD} = "[REDACTED]"`);
  await expect(sent).not.toContainText("synthetic-only-1");
  await expect(panel.getByText(/It isn't shown here, so checking doesn't give the hint away\./)).toBeVisible();
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const result = await new AxeBuilder({ page }).include(".coach-context").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(result.violations.map((v) => v.id), theme).toEqual([]);
  }
  expect(await used()).toBe(before); // checking is free

  // Code changed after checking: not sendable until checked again.
  await replaceEditorContent(page, CODE.replace("return new int[0];", "return null;"));
  await expect(panel.getByText("Your code changed since this was checked, so it isn't what would be sent.")).toBeVisible();
  await expect(panel.getByRole("button", { name: "Ask for the level 1 hint" })).toBeDisabled();
  await panel.getByRole("button", { name: "Check again" }).click();
  await expect(panel.getByLabel("Exactly what's sent: Your code")).toContainText("return null;");
  await panel.getByRole("button", { name: "Ask for the level 1 hint" }).click();
  await expect(coach.getByText("Level 1 · Nudge")).toBeVisible();
  expect(await used()).toBe(before + 1);

  // The next level says what was seen; Cancel sends nothing.
  await coach.getByRole("button", { name: "Unlock level 2: Concept" }).click();
  await expect(panel.getByText("You've seen level 1 (Nudge) for this problem, so this one goes further.")).toBeVisible();
  await panel.getByRole("button", { name: "Cancel" }).click();
  await expect(coach.getByText("Cancelled. Nothing was sent.")).toBeVisible();
  expect(await used()).toBe(before + 1);
});
