import { expect, test } from "./fixtures";
import { STRONG, TRACK, api, newAccount, signIn } from "./preparation-journey";

/**
 * Related practice for an accepted improvement (Volume 13, prompt 4; docs/ACCEPTED_ACTIONS.md),
 * against the real API: a retry and then a follow-up are listed under the improvement on the plan,
 * in order, each with its own score; the follow-up says it's a different question; nothing ticks the
 * action or says it worked. Synthetic data.
 */
const Q = "e-accuracy-0";
const FOLLOW = "e-accuracy-1";
const LOWER =
  "I checked the patient and looked at the chart. I asked a colleague and we talked about it, then I wrote " +
  "it down for the next shift so everyone knew what had happened on the ward that night. It was a busy " +
  "shift and there were a lot of patients, so we did our best as a team and kept going until the morning.";

test("a retry and a follow-up are listed under the improvement, each with its own score, and nothing ticks it", async ({ page, request }) => {
  const acct = await newAccount(request, "related");
  const iv = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/interviews", { kind: "questions", question_ids: [Q], duration_minutes: 15 });
  await api(request, acct.auth, "post", `/api/v1/interviews/${iv.id}/answers`, { question_index: 0, answer: STRONG, source: "typed" });
  const review = await api<{ improvements: { key: string; title: string }[] }>(request, acct.auth, "get", `/api/v1/interviews/${iv.id}/review`);
  const imp = review.improvements[0]!;
  const action = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/me/actions", { source: { interview_id: iv.id, key: imp.key } });
  const retry = (await api<{ latest: { id: string; score: number } }>(request, acct.auth, "post", `/api/v1/interviews/${iv.id}/questions/0/retries`, { answer: STRONG })).latest;
  const follow = await api<{ id: string; score: number }>(request, acct.auth, "post", `/api/v1/careers/${TRACK}/questions/${FOLLOW}/answers`, {
    answer: LOWER, follows_up_answer_id: retry.id,
  });
  // An unrelated answer to the same question on its own page: no stored link, never listed.
  await api(request, acct.auth, "post", `/api/v1/careers/${TRACK}/questions/${Q}/answers`, { answer: STRONG });
  await signIn(page, acct.email);

  await page.goto("/plan");
  const section = page.getByRole("region", { name: "Improvements you accepted (1)" });
  await section.getByText("Related practice since you accepted it (2)").click();
  const items = section.locator(".related-practice li");
  await expect(items).toHaveCount(2);
  await expect(items.nth(0)).toContainText(`Retry: Checking your patient assessment work`);
  await expect(items.nth(0)).toContainText(`${retry.score}/100`);
  await expect(items.nth(1)).toContainText("Follow-up: Checking your medication administration work");
  await expect(items.nth(1)).toContainText(`${follow.score}/100`);
  await expect(items.nth(1)).toContainText("A different question about the same thing: not a retry");
  await expect(section).not.toContainText(/worked|improved/i);
  const after = await api<{ status: string; done_at: string | null }>(request, acct.auth, "get", `/api/v1/me/actions/${action.id}`);
  expect(after.status).toBe("open");
  expect(after.done_at).toBeNull();
});
