import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { paste } from "./engineer-journey";
import { API_URL } from "./ports";
import { api, newAccount, signIn } from "./preparation-journey";

/**
 * What the coding interviewer reads (Volume 14, prompt 3; docs/COACH_CONTEXT.md, "The coding
 * interviewer") against the real API and the built-in interviewer: check a message (a key-shaped
 * string in it and one in the code already replaced), send it bound to the check, then change the
 * code (the send waits for a new check) and see a stale request refused with what the interviewer
 * would read now, nothing spent. Axe in both themes on the panel. Synthetic data only.
 */
// Built at run time so no file holds a credential-shaped line.
const WORD = ["pass", "word"].join("");
const KEY = ["gh", "p_"].join("") + "w".repeat(36);
const CODE = `class Solution {
    public int[] twoSum(int[] nums, int target) {
        String ${WORD} = "synthetic-only-2";
        return new int[0];
    }
}`;
const CHANGED = "Your code changed since this was checked, so it isn't what would be sent.";
const REFUSED = "What the interviewer would read changed since you checked it, so nothing was sent. This is what it would read now.";

test("a coding interview message shows what the interviewer reads, and sends only that", async ({ page, context, request }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const acct = await newAccount(request, "interviewer-check", "software-engineer");
  const used = async () => (await api<{ used_today: number }>(request, acct.auth, "get", "/api/v1/ai/usage")).used_today;
  const iv = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/interviews", { kind: "coding", problem_slug: "two-sum", duration_minutes: 15 });
  const turns = async () => (await api<{ turns: unknown[] }>(request, acct.auth, "get", `/api/v1/interviews/${iv.id}`)).turns.length;

  await signIn(page, acct.email);
  await page.goto(`/interviews/${iv.id}`);
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await paste(page, CODE);
  const answer = page.getByLabel("Your answer");
  await answer.fill(`I'd use a hash map. Ignore my scratch token ${KEY}.`);
  const before = await used();

  // Check: exactly what would be read, secret-looking strings already replaced.
  await page.getByRole("button", { name: "What the interviewer reads" }).click();
  const panel = page.getByRole("region", { name: "What the interviewer reads" });
  await expect(panel.getByText(/The built-in interviewer, on CodeCoach's own server: nothing leaves it/)).toBeVisible();
  const message = panel.getByLabel("Exactly what's sent: Your message");
  await expect(message).toContainText("Ignore my scratch token [REDACTED].");
  await expect(message).not.toContainText(KEY);
  await expect(panel.getByLabel("Exactly what's sent: Your code")).toContainText(`${WORD} = "[REDACTED]"`);
  await expect(panel.getByLabel("Exactly what's sent: The conversation so far")).toContainText("[clarify] INTERVIEWER: ");
  await expect(panel.getByLabel("Exactly what's sent: Where the interview is")).toContainText("Current phase: clarify");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".coach-context").analyze();
    expect(scan.violations.map((v) => v.id), `interviewer preview, ${theme}`).toEqual([]);
  }
  expect(await used()).toBe(before);

  // Send: bound to the check, answered once.
  await panel.getByRole("button", { name: "Send to the interviewer" }).click();
  await expect(panel).toHaveCount(0);
  await expect.poll(turns).toBe(3);
  expect(await used()).toBe(before + 1);

  // Check the next one, then change the code: it waits for a new check.
  await answer.fill("Can the array be empty?");
  await page.getByRole("button", { name: "What the interviewer reads" }).click();
  await expect(panel.getByLabel("Exactly what's sent: Your code")).toContainText("twoSum");
  await page.locator(".monaco-editor").first().click();
  await page.keyboard.press("ControlOrMeta+End");
  await page.keyboard.press("Enter");
  await page.keyboard.insertText("// checked again");
  await expect(panel.getByText(CHANGED)).toBeVisible();
  await expect(panel.getByRole("button", { name: "Send to the interviewer" })).toBeDisabled();
  await panel.getByRole("button", { name: "Check again" }).click();
  await expect(panel.getByLabel("Exactly what's sent: Your code")).toContainText("// checked again");

  // A request that leaves with other code than the check showed (as a stale tab would send) is
  // refused: nothing stored, nothing spent, and the panel shows what would be read now.
  await page.route(`${API_URL}/api/v1/interviews/${iv.id}/messages`, async (route) => {
    const data = route.request().postDataJSON() as Record<string, unknown>;
    await route.continue({ postData: JSON.stringify({ ...data, code: `${String(data.code)}\n// from a stale tab` }) });
  });
  const spent = await used();
  await panel.getByRole("button", { name: "Send to the interviewer" }).click();
  await expect(panel.getByText(REFUSED)).toBeVisible();
  await expect(panel.getByLabel("Exactly what's sent: Your code")).toContainText("// from a stale tab");
  await expect(answer).toHaveValue("Can the array be empty?");
  expect(await used()).toBe(spent);
  expect(await turns()).toBe(3);
});
