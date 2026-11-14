import { navTo, chooseJob, expect, test, type Page } from "./fixtures";

const SOLUTION = `class Solution {
    public int[] twoSum(int[] nums, int target) {
        for (int i = 0; i < nums.length; i++) {
            for (int j = i + 1; j < nums.length; j++) {
                if (nums[i] + nums[j] == target) return new int[] {i, j};
            }
        }
        return new int[0];
    }
}`;

const judging = process.env.E2E_JUDGE === "1";

async function replaceEditorContent(page: Page, code: string) {
  const editor = page.locator(".monaco-editor").first();
  await editor.click();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.press("Delete");
  // Paste, as a learner moving code from their IDE would. (keyboard.insertText of
  // pre-indented code would be re-indented by Monaco on every newline.)
  await page.evaluate((text) => navigator.clipboard.writeText(text), code);
  await page.keyboard.press("ControlOrMeta+V");
}

async function editorText(page: Page): Promise<string> {
  // Monaco renders spaces as non-breaking spaces in its view layer.
  const text = await page.locator(".monaco-editor .view-lines").first().textContent();
  return (text ?? "").replace(/\u00a0/g, " ");
}

test("guest journey: try it, code, hints, review, submit, progress", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Practice like it's the real interview");
  await page.screenshot({ path: "e2e/screenshots/01-landing.png", fullPage: true });

  await page.getByRole("button", { name: /try it now/i }).click();
  await page.getByRole("button", { name: "Start this problem" }).click(); // the optional welcome
  await expect(page).toHaveURL(/\/problems\/two-sum$/);
  await expect(page.getByRole("heading", { name: "Two Sum", level: 1 })).toBeVisible();
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await expect(page.getByText("Guest", { exact: true })).toBeVisible();

  // Real typing in the real Monaco editor.
  await replaceEditorContent(page, SOLUTION);
  await expect(page.getByText("Saved on device")).toBeVisible();

  // Hints unlock one level at a time.
  await page.getByRole("button", { name: "Get a hint" }).click();
  await expect(page.getByText("Level 1 · Nudge")).toBeVisible();
  await page.getByRole("button", { name: "Unlock level 2: Concept" }).click();
  await expect(page.getByText("Level 2 · Concept")).toBeVisible();
  await expect(page.getByText(/HashMap/).first()).toBeVisible();

  // Structured review flags the nested loop and links to the line.
  await page.getByRole("tab", { name: "Code review" }).click();
  await page.getByRole("button", { name: "Review my code" }).click();
  // What the coach will read is shown first; nothing is sent until it's approved.
  await expect(page.getByRole("heading", { name: "What the coach will read" })).toBeVisible();
  await page.getByRole("button", { name: "Send for review" }).click();
  await expect(page.getByText(/Nested loops make this roughly O\(n\^2\)/).first()).toBeVisible();
  await page.getByRole("button", { name: "line 3" }).click();
  await expect(page.locator(".editor-line--flagged")).toHaveCount(1);
  await page.screenshot({ path: "e2e/screenshots/02-workspace-review.png" });

  // Submit: stored, honest about execution being disabled.
  await page.getByRole("button", { name: /^(Submit|Save attempt)$/ }).click(); // "Save attempt" when no judge is configured
  if (judging) {
    // The O(n^2) solution is correct, so the real judge passes it.
    await expect(page.getByText("All tests passed. Nice work.")).toBeVisible({ timeout: 60_000 });
  } else {
    // Execution off: the button said "Save attempt", the page says why, and the result is honest.
    await expect(page.getByText("Code can't run on this server.")).toBeVisible();
    await expect(page.getByText("Saved, but not run yet.")).toBeVisible();
    await expect(page.getByText("Queued", { exact: true })).toBeVisible();
  }

  // Draft survives a reload.
  await page.reload();
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await expect.poll(() => editorText(page)).toContain("nums[i] + nums[j] == target");

  // Progress reflects the activity.
  await navTo(page, "Dashboard");
  const summary = page.getByRole("region", { name: "Summary" });
  await expect(summary.getByText("Coaching used")).toBeVisible();
  await expect(summary.getByText("3", { exact: true })).toBeVisible(); // 2 hints + 1 review
  if (!judging) await expect(page.getByText(/without a pass/).first()).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/03-dashboard.png", fullPage: true });

  // History keeps the attempt and the AI feedback.
  await navTo(page, "History");
  // Wait for the History page itself: the dashboard (still on screen while History loads) has
  // "Two Sum" links of its own, so an unscoped check could pass against the wrong page.
  await expect(page).toHaveURL(/\/history/);
  await expect(page.getByRole("heading", { name: "History", level: 1 })).toBeVisible();
  const filters = page.getByRole("search", { name: "Filter history" });
  await filters.getByLabel("Activity").selectOption("code_submission");
  await expect(page.getByRole("listitem").filter({ hasText: "Two Sum" }).first()).toBeVisible();
  await filters.getByLabel("Activity").selectOption("coaching");
  await expect(page.getByText(/Code review/).first()).toBeVisible();
});

test("account journey: register, filter library, sign out, sign in", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Name").fill("Ada");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("weak");
  await chooseJob(page, "software-engineer");
  await page.getByRole("form", { name: "Create your account" }).getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText(/at least 10 characters|String should have at least 10/i).last()).toBeVisible();
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByRole("form", { name: "Create your account" }).getByRole("button", { name: "Create account" }).click();
  // New accounts are asked for the emailed code first; it can be done later.
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click(); // the optional welcome
  // New accounts are welcomed; this journey goes straight to the dashboard.
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { level: 1, name: "Your interview practice" })).toBeVisible();
  await navTo(page, "Questions");
  await expect(page).toHaveURL(/\/problems$/);

  await page.getByRole("button", { name: /stacks/i }).click();
  await expect(page).toHaveURL(/topic=stacks/);
  const list = page.getByRole("region", { name: "Problem list" });
  await expect(list.getByRole("link", { name: /Valid Parentheses/ })).toBeVisible();
  await expect(list.getByRole("link", { name: /Two Sum/ })).toHaveCount(0);
  await page.screenshot({ path: "e2e/screenshots/04-library-filtered.png" });

  await page.getByRole("button", { name: "Sign out" }).click();
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { level: 1, name: "Your interview practice" })).toBeVisible();

  // Settings: rename, then permanently delete the account.
  await page.getByRole("link", { name: /account settings/ }).click();
  await page.getByLabel("Display name").fill("Ada L.");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByRole("banner").getByText("Ada L.")).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/09-settings.png", fullPage: true });
  const danger = page.getByRole("form", { name: "Delete account" });
  await danger.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await danger.getByLabel('Type "DELETE" to confirm').fill("DELETE");
  await danger.getByRole("button", { name: "Delete my account" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
  // The account is really gone.
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toContainText("Incorrect email or password");
});
