import { expect, test } from "./fixtures";
import { api, newAccount, signIn } from "./preparation-journey";

/**
 * A dispute counts wherever the advice is reused (Volume 14, prompt 9; docs/DISPUTES.md), against
 * the real API: a round whose top improvement is then disputed on every answer missing it, and the
 * saved review item's answer disputed overall: the summary stops suggesting it and says why, the
 * review queue holds the item under "You disputed this" (and Due now doesn't count it); counted
 * again, both come back. The feedback itself never changes. Synthetic data.
 */
const STRONG = "On a busy night shift I noticed a patient whose breathing had changed, so I checked their vital signs, escalated to the charge nurse and documented every step. As a result the patient was stable within the hour and I learned to reassess sooner.";
const WEAK = "Patient assessment is something every nurse does on the ward. It is part of the job and it is important to do it well because patients depend on nurses. I do it on my shifts like everyone else.";
const QUESTIONS = ["e-good-0", "e-steps-0", "e-time-0", "e-mistake-0", "e-explain-0"];

type Point = { label: string; covered: boolean };
type Item = { key: string; index: number; question_id: string; feedback: { id: string; points: Point[] } | null };
type Review = { improvements: { key: string; title: string }[]; disputed_points: { label: string }[]; items: Item[] };

test("a disputed point leaves the summary and the queue, says so in each, and comes back when counted again", async ({ page, request }) => {
  const acct = await newAccount(request, "disputes-everywhere");
  const iv = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/interviews", { kind: "questions", track: "registered-nurse", question_ids: QUESTIONS });
  for (const [i, a] of [STRONG, WEAK, WEAK, null, STRONG].entries()) {
    if (a === null) await api(request, acct.auth, "post", `/api/v1/interviews/${iv.id}/skip`, { question_index: i });
    else await api(request, acct.auth, "post", `/api/v1/interviews/${iv.id}/answers`, { question_index: i, answer: a, source: "typed" });
  }
  const before = await api<Review>(request, acct.auth, "get", `/api/v1/interviews/${iv.id}/review`);
  const label = before.improvements[0]!.title;
  const missing = before.items.filter((i) => i.feedback?.points.some((p) => !p.covered && p.label === label));
  const saved = missing[0]!;
  await api(request, acct.auth, "post", "/api/v1/me/reviews", { track: "registered-nurse", question_id: saved.question_id, session_id: iv.id });
  const flags: { answer: string; id: string }[] = [];
  for (const m of missing) {
    const r = await api<{ flags: { id: string; criterion: string }[] }>(request, acct.auth, "post", `/api/v1/me/answers/${m.feedback!.id}/flags`, { criterion: label, kind: "disagree", note: "I did" });
    flags.push({ answer: m.feedback!.id, id: r.flags.find((f) => f.criterion === label)!.id });
  }
  const overall = await api<{ flags: { id: string; criterion: string }[] }>(request, acct.auth, "post", `/api/v1/me/answers/${saved.feedback!.id}/flags`, { criterion: "Overall", kind: "disagree", note: "Not fair" });
  flags.push({ answer: saved.feedback!.id, id: overall.flags.find((f) => f.criterion === "Overall")!.id });

  await signIn(page, acct.email);
  await page.goto(`/interviews/${iv.id}`);
  const left = page.getByRole("region", { name: /Not suggested \(\d+\)/ });
  await expect(left).toContainText(`Not suggested: “${label}”`);
  await expect(left).toContainText("Left out because of feedback you disputed, not because there's nothing to practise.");
  await expect(page.locator(".review__improvements")).not.toContainText(label);

  await page.goto("/reviews");
  await expect(page.getByRole("heading", { name: "You disputed this (1)" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Due now (0)" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Count it again (see the dispute)" })).toBeVisible();

  // Counted again: each place comes back.
  for (const f of flags) await api(request, acct.auth, "post", `/api/v1/me/answers/${f.answer}/flags/${f.id}/reinstate`);
  await page.goto(`/interviews/${iv.id}`);
  await expect(page.locator(".review__improvements")).toContainText(label);
  await expect(page.getByRole("region", { name: /Not suggested/ })).toHaveCount(0);
  await page.goto("/reviews");
  await expect(page.getByRole("heading", { name: /You disputed this/ })).toHaveCount(0);
  const after = await api<Review>(request, acct.auth, "get", `/api/v1/interviews/${iv.id}/review`);
  expect(after.items.map((i) => i.feedback)).toEqual(before.items.map((i) => i.feedback)); // never rewritten
});
