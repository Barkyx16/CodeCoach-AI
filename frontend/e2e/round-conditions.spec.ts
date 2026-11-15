import { expect, test } from "./fixtures";
import { STRONG, TRACK, api, newAccount, signIn } from "./preparation-journey";

/**
 * Conditions for interview-round answers (Volume 13, prompt 3; docs/ATTEMPT_CONDITIONS.md), against
 * the real API: a lesson read before a round marks the answer to the question it prepares, and only
 * that one; the round's results give one line per answer with the round's format; the question page
 * shows the same, recorded when the answer was saved. Synthetic data.
 */
const PREPARED = "e-steps-7"; // the lesson "SBAR for handoffs and escalation" prepares for it
const OTHER = "e-accuracy-0";

test("a round's answers say what in-app help was in play, recorded when they were saved", async ({ page, request }) => {
  const acct = await newAccount(request, "round-cond");
  await api(request, acct.auth, "post", "/api/v1/me/learn/units/rn-sbar-handoff/events", { kind: "read", version: 1 });
  const iv = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/interviews", {
    kind: "questions", question_ids: [PREPARED, OTHER], duration_minutes: 15,
  });
  for (const index of [0, 1]) {
    await api(request, acct.auth, "post", `/api/v1/interviews/${iv.id}/answers`, { question_index: index, answer: STRONG, source: "typed" });
  }
  // A lesson read after the round belongs to the next answer, never to these.
  await api(request, acct.auth, "post", "/api/v1/me/learn/units/rn-sbar-handoff/events", { kind: "read", version: 1 });
  await signIn(page, acct.email);

  await page.goto(`/interviews/${iv.id}?item=q0`);
  const first = page.getByRole("article", { name: /^1\. / });
  await expect(first.locator("p").filter({ hasText: /^In-app help before this answer:/ })).toHaveText("In-app help before this answer: Hint shown");
  await expect(first.getByText("A 15-minute timed mock interview; no follow-up.")).toBeVisible();
  await page.goto(`/interviews/${iv.id}?item=q1`);
  const second = page.getByRole("article", { name: /^2\. / });
  await expect(second.locator("p").filter({ hasText: /^In-app help before this answer:/ })).toHaveText("In-app help before this answer: No in-app help recorded");

  await page.goto(`/careers/${TRACK}/questions/${PREPARED}`);
  const past = page.locator(".card").filter({ has: page.getByRole("heading", { name: "Your past answers" }) });
  await past.getByRole("button").first().click();
  const shown = page.locator(".attempt-conditions");
  await expect(shown.locator("p").filter({ hasText: /^In-app help before this attempt:/ })).toHaveText("In-app help before this attempt: Hint shown");
  await expect(shown).toContainText("How it was given: A 15-minute timed mock interview; no follow-up. (the format, not help)");
});
