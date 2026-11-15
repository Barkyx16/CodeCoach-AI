import type { APIRequestContext } from "@playwright/test";

import { expect, test } from "./fixtures";
import { BASELINE, JUDGE_NEEDED, NOT_LINKED, PROBLEM, PROBLEM_TITLE, RESUBMISSION, SE_TRACK, paste, type Sub } from "./engineer-journey";
import { API_URL } from "./ports";
import { api, newAccount, signIn, type Account } from "./preparation-journey";

/**
 * The software engineer's journey's branches (Volume 13, prompt 10; docs/PREPARATION_JOURNEY.md),
 * each on a fresh account, seeded through the API up to the point it tests, then checked in the
 * browser. Each has a negative control: with its protection removed, it fails. The resubmission
 * branch needs the real judge (E2E_JUDGE=1); the other two run in every e2e run. Synthetic data.
 */

const REFUSED = "What the coach would read changed since you checked it, so nothing was sent. This is what it would read now.";

const usedToday = async (request: APIRequestContext, acct: Account) =>
  (await api<{ used_today: number }>(request, acct.auth, "get", "/api/v1/ai/usage")).used_today;

async function submitApi(request: APIRequestContext, acct: Account, code: string): Promise<Sub> {
  const key = `branch-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  const created = await api<Sub>(request, acct.auth, "post", "/api/v1/submissions", { problem_slug: PROBLEM, language: "java", source_code: code, mode: "submit", client_request_id: key });
  let sub = created;
  await expect.poll(async () => {
    sub = await api<Sub>(request, acct.auth, "get", `/api/v1/submissions/${created.id}`);
    return sub.is_terminal;
  }, { timeout: 120_000, intervals: [500] }).toBe(true);
  return sub;
}

test("a coach request whose code changed after its preview is refused, and nothing is sent", async ({ page, context, request }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const acct = await newAccount(request, "engineer-changed", SE_TRACK);

  // By the API: the preview's fingerprint with other code is refused, with what it would read now.
  const preview = await api<{ context_fingerprint: string }>(request, acct.auth, "post", "/api/v1/ai/review/preview", { problem_slug: PROBLEM, source_code: BASELINE, share_verdict: false });
  const before = await usedToday(request, acct);
  const changed = BASELINE.replace("{0, 1}", "{1, 0}");
  const r = await request.post(`${API_URL}/api/v1/ai/review`, { headers: acct.auth, data: { problem_slug: PROBLEM, source_code: changed, share_verdict: false, approved_context: preview.context_fingerprint } });
  expect(r.status()).toBe(409);
  const body = (await r.json()) as { error: { code: string; details: { preview?: { items: { key: string; text: string }[] } } } };
  expect(body.error.code).toBe("context_changed");
  expect(body.error.details.preview?.items.find((i) => i.key === "code")?.text).toBe(changed);
  expect(await usedToday(request, acct)).toBe(before);

  // In the browser: a request that leaves with other code than the preview showed (as a stale tab
  // would send) is refused, the page says so and shows what the coach would read now.
  await signIn(page, acct.email);
  await page.goto(`/problems/${PROBLEM}`);
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await paste(page, BASELINE);
  await page.getByRole("tab", { name: "Code review" }).click();
  await page.getByRole("button", { name: "Review my code" }).click();
  const panel = page.locator("section").filter({ has: page.getByRole("heading", { name: "What the coach will read" }) });
  await expect(panel.getByLabel("Exactly what's sent: Your code")).toContainText("{0, 1}");
  await page.route(`${API_URL}/api/v1/ai/review`, async (route) => {
    const data = route.request().postDataJSON() as Record<string, unknown>;
    await route.continue({ postData: JSON.stringify({ ...data, source_code: changed }) });
  });
  await panel.getByRole("button", { name: "Send for review" }).click();
  await expect(page.getByText(REFUSED)).toBeVisible();
  await expect(panel.getByLabel("Exactly what's sent: Your code")).toContainText("{1, 0}");
  await expect(page.getByText("What's working")).toHaveCount(0);
  expect(await usedToday(request, acct)).toBe(before);
});

test("another account's submission isn't found, by its page or by the coach", async ({ page, request }) => {
  const owner = await newAccount(request, "engineer-owner", SE_TRACK);
  const key = `owner-${Date.now()}`;
  const sub = await api<{ id: string }>(request, owner.auth, "post", "/api/v1/submissions", { problem_slug: PROBLEM, language: "java", source_code: BASELINE, mode: "submit", client_request_id: key });
  const other = await newAccount(request, "engineer-other", SE_TRACK);

  await signIn(page, other.email);
  await page.goto(`/history/submissions/${sub.id}`);
  await expect(page.getByText("This submission isn't available")).toBeVisible();
  await expect(page.getByText(BASELINE.split("\n")[1]!.trim())).toHaveCount(0);

  const get = await request.get(`${API_URL}/api/v1/submissions/${sub.id}`, { headers: other.auth });
  expect(get.status()).toBe(404);
  expect(((await get.json()) as { error: { code: string } }).error.code).toBe("not_found");
  for (const [path, data] of [
    ["/api/v1/ai/review/preview", { problem_slug: PROBLEM, source_code: BASELINE, submission_id: sub.id, share_verdict: true }],
    ["/api/v1/ai/explain-failure/preview", { submission_id: sub.id, share_compile_output: true, share_failing_test: true }],
  ] as const) {
    const res = await request.post(`${API_URL}${path}`, { headers: other.auth, data });
    expect(res.status(), path).toBe(404);
  }
  const conditions = await api<{ submissions: Record<string, unknown> }>(request, other.auth, "post", "/api/v1/me/attempt-conditions", { submission_ids: [sub.id], answer_ids: [] });
  expect(Object.keys(conditions.submissions)).toEqual([]);
  // The owner still has it.
  expect((await request.get(`${API_URL}/api/v1/submissions/${sub.id}`, { headers: owner.auth })).status()).toBe(200);
});

test.describe("with the real judge", () => {
  test.skip(process.env.E2E_JUDGE !== "1", `This branch ${JUDGE_NEEDED}.`);

  test("a judged resubmission keeps its own verdict and help, compared with the first by the one rule", async ({ page, request }) => {
    test.setTimeout(240_000);
    const acct = await newAccount(request, "engineer-resubmit", SE_TRACK);
    // A level 1 hint, then the baseline and a resubmission, judged in the sandbox.
    const hint = await api<{ context_fingerprint: string }>(request, acct.auth, "post", "/api/v1/ai/hint/preview", { problem_slug: PROBLEM, source_code: BASELINE, level: 1 });
    await api(request, acct.auth, "post", "/api/v1/ai/hint", { problem_slug: PROBLEM, source_code: BASELINE, level: 1, approved_context: hint.context_fingerprint });
    const first = await submitApi(request, acct, BASELINE);
    const second = await submitApi(request, acct, RESUBMISSION);
    expect([first.status, second.status]).toEqual(["FAILED", "PASSED"]);
    // An improvement accepted from a coding interview on the same problem.
    const iv = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/interviews", { kind: "coding", problem_slug: PROBLEM, duration_minutes: 15, purpose: "practice" });
    await api(request, acct.auth, "post", `/api/v1/interviews/${iv.id}/finish`, { code: BASELINE });
    const review = await api<{ improvements: { key: string; title: string }[] }>(request, acct.auth, "get", `/api/v1/interviews/${iv.id}/review`);
    await api(request, acct.auth, "post", "/api/v1/me/actions", { source: { kind: "interview_improvement", interview_id: iv.id, key: review.improvements[0]!.key }, recurrence: "weekly" });

    await signIn(page, acct.email);
    // Each attempt's help is its own: the hint belongs to the first attempt after it.
    await page.goto("/history?type=code_submission");
    const rows = page.getByRole("listitem").filter({ hasText: PROBLEM_TITLE });
    await expect(rows).toHaveCount(2);
    await expect(rows.filter({ hasText: "In-app help: Hint shown" })).toHaveCount(1);
    await expect(rows.filter({ hasText: "In-app help: No in-app help recorded" })).toHaveCount(1);
    await page.goto(`/history/submissions/${second.id}`);
    await expect(page.locator(".attempt-conditions")).toContainText("In-app help before this attempt: No in-app help recorded");
    await expect(page.getByRole("heading", { name: "Result" }).locator("..")).toContainText(`${second.result!.passed_count} of ${second.result!.total_count} tests passed`);
    // Compared with the first: the help differed (the hint was before the first only), so partly.
    const compared = page.getByRole("region", { name: "Compared with your previous submission" });
    await expect(compared).toContainText(/^Compared with your previous submission.*Failed.*Passed.*Partly comparable: the in-app help differed: before the earlier one, hint shown; before the later one, none recorded/);
    // The improvement doesn't claim the resubmission as its evidence: no practice is linked to it.
    await page.goto("/plan");
    const accepted = page.getByRole("region", { name: "Improvements you accepted (1)" });
    await expect(accepted.getByText(NOT_LINKED)).toBeVisible();
    await expect(accepted).not.toContainText(/improv(ed|ement shown)|better than/i);
  });
});
