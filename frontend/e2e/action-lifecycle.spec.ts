import { expect, test } from "./fixtures";
import { api, newAccount, signIn } from "./preparation-journey";

/**
 * Archiving, unarchiving and deleting an accepted improvement on the plan page (Volume 14, prompt 5;
 * docs/ACCEPTED_ACTIONS.md, "Archive and delete") against the real API: each shows what it would do
 * first; archived, it's off the schedule and listed under Archived; unarchived, it's back with its
 * weeks; deleted, it's gone and its suggestion can be accepted again. Synthetic data only.
 */
test("an accepted improvement is archived, unarchived and deleted, each as previewed", async ({ page, request }) => {
  const acct = await newAccount(request, "action-lifecycle", "software-engineer");
  const iv = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/interviews", { kind: "coding", problem_slug: "two-sum", duration_minutes: 15 });
  await api(request, acct.auth, "post", `/api/v1/interviews/${iv.id}/finish`, { code: "class Solution { public int[] twoSum(int[] n, int t) { return new int[0]; } }" });
  const review = await api<{ improvements: { key: string; title: string; action_id: string | null }[] }>(request, acct.auth, "get", `/api/v1/interviews/${iv.id}/review`);
  const imp = review.improvements[0]!;
  const action = await api<{ id: string; title: string }>(request, acct.auth, "post", "/api/v1/me/actions", { source: { interview_id: iv.id, key: imp.key }, recurrence: "weekly" });
  const monday = new Date(Date.now() + 2 * 86_400_000).toISOString().slice(0, 10);
  await api(request, acct.auth, "post", `/api/v1/me/actions/${action.id}/occurrences`, { on_date: monday, weeks: 2 });
  const scheduled = async () => (await api<unknown[]>(request, acct.auth, "get", `/api/v1/me/schedule?from=${monday}&to=${monday}`)).length;
  expect(await scheduled()).toBe(1);

  await signIn(page, acct.email);
  await page.goto("/plan");
  const section = page.locator("#accepted-actions");
  await expect(section.getByRole("heading", { name: "Improvements you accepted (1)" })).toBeVisible();

  // Archive: what it keeps first, then off the plan's list and the schedule.
  await section.getByRole("button", { name: `Archive: ${action.title}` }).click();
  const plan = section.getByRole("group", { name: "What this will do" });
  await expect(plan).toContainText("Off your schedule while it's archived");
  await plan.getByRole("button", { name: "Archive this improvement" }).click();
  await expect(section.getByRole("status")).toContainText(`Archived ${action.title}. Unarchive it any time.`);
  await expect(section.getByRole("heading", { name: "Improvements you accepted (0)" })).toBeVisible();
  expect(await scheduled()).toBe(0);

  // Unarchive: back, with its weeks.
  await section.getByText("Archived (1)").click();
  await section.getByRole("button", { name: `Unarchive: ${action.title}` }).click();
  await expect(section.getByRole("heading", { name: "Improvements you accepted (1)" })).toBeVisible();
  expect(await scheduled()).toBe(1);

  // Delete: its weeks go, and the suggestion can be accepted again.
  await section.getByRole("button", { name: `Delete: ${action.title}` }).click();
  const del = section.getByRole("group", { name: "What this will do" });
  await expect(del).toContainText("Occurrence:");
  await del.getByRole("button", { name: "Delete this improvement" }).click();
  await expect(section.getByRole("status")).toContainText(`Deleted ${action.title}.`);
  expect(await scheduled()).toBe(0);
  const after = await api<{ improvements: { key: string; action_id: string | null }[] }>(request, acct.auth, "get", `/api/v1/interviews/${iv.id}/review`);
  expect(after.improvements.find((i) => i.key === imp.key)?.action_id).toBeNull();
});
