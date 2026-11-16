import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { api, newAccount, signIn } from "./preparation-journey";

/**
 * Hints inside a coding interview (Volume 17, prompt 4) against the real API and the built-in coach:
 * the panel shows what the coach reads first, asks for the level 1 hint bound to that, lists it with
 * its time and message count, and the interview's own record holds it; after a reload the panel lists
 * it again; asking again for level 1 through the API is the same hint with no second request. Axe in
 * both themes on the panel. Synthetic account.
 */
test("a hint asked for inside the coding interview is checked first and recorded with it", async ({ page, request }) => {
  const acct = await newAccount(request, "interview-hints", "software-engineer");
  const iv = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/interviews", { kind: "coding", problem_slug: "two-sum", duration_minutes: 15 });
  const used = async () => (await api<{ used_today: number }>(request, acct.auth, "get", "/api/v1/ai/usage")).used_today;

  await signIn(page, acct.email);
  await page.goto(`/interviews/${iv.id}`);
  await expect(page.locator(".monaco-editor")).toBeVisible();
  const panel = page.locator(".interview-hints");
  await panel.getByText("Hints", { exact: true }).click();
  await panel.getByRole("button", { name: "Get a hint" }).click();
  await expect(panel.getByRole("region", { name: "What the coach reads" }).or(panel.getByText("Your code").first())).toBeVisible();
  const before = await used();
  await panel.getByRole("button", { name: "Ask for the level 1 hint" }).click();
  const list = panel.getByRole("list", { name: "Hints in this interview" });
  await expect(list.getByText("Level 1 · Nudge")).toBeVisible();
  await expect(list).toContainText("after 1 message");
  const recorded = await api<{ hints: { level: number }[] }>(request, acct.auth, "get", `/api/v1/interviews/${iv.id}`);
  expect(recorded.hints.map((h) => h.level)).toEqual([1]);

  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".interview-hints").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }

  await page.reload();
  await expect(page.locator(".interview-hints").getByRole("list", { name: "Hints in this interview" }).getByText("Level 1 · Nudge")).toBeVisible();
  const n = await used();
  const again = await api<{ repeated: boolean }>(request, acct.auth, "post", `/api/v1/interviews/${iv.id}/hint`, { level: 1 });
  expect(again.repeated).toBe(true);
  expect(await used()).toBe(n); // nothing asked of the coach again
  expect(n).toBeGreaterThanOrEqual(before);
});
