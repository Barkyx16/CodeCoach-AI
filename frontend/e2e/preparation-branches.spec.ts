import type { APIRequestContext } from "@playwright/test";

import { expect, test } from "./fixtures";
import {
  BASELINE_Q, IMPROVEMENT, JD, MIDDLING, STRONG, TRACK, api, iso, newAccount, signIn, type Account,
} from "./preparation-journey";
import { API_URL } from "./ports";

/**
 * The preparation journey's branches (Volume 12, prompt 10; docs/PREPARATION_JOURNEY.md), each on a
 * fresh synthetic account seeded through the API up to the point it tests, then checked in the
 * browser by what the learner sees: disputed advice, an incompatible comparison, stale evidence, a
 * deletion race, a lost response and another account's ids. Each has a negative control (the
 * protection removed, the branch fails), listed in the journey record.
 */

interface Seeded { acct: Account; targetId: string; interviewId: string; key: string }

/** A target, the targeted session answered (72, 52, 72), and its review's improvement key. */
async function seeded(request: APIRequestContext, prefix: string): Promise<Seeded> {
  const acct = await newAccount(request, prefix);
  const t = await api<{ id: string; targeted_session: { round: Record<string, unknown> } }>(request, acct.auth, "post", "/api/v1/targets", { title: "Ward nurse", description: JD });
  const iv = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/interviews", { kind: "questions", ...t.targeted_session.round });
  for (const [i, answer] of [STRONG, MIDDLING, STRONG].entries()) {
    await api(request, acct.auth, "post", `/api/v1/interviews/${iv.id}/answers`, { question_index: i, answer, source: "typed" });
  }
  const review = await api<{ improvements: { key: string; title: string }[] }>(request, acct.auth, "get", `/api/v1/interviews/${iv.id}/review`);
  return { acct, targetId: t.id, interviewId: iv.id, key: review.improvements.find((x) => x.title === IMPROVEMENT)!.key };
}

async function accept(request: APIRequestContext, s: Seeded): Promise<string> {
  return (await api<{ id: string }>(request, s.acct.auth, "post", "/api/v1/me/actions", { source: { interview_id: s.interviewId, key: s.key } })).id;
}

async function kitWith(request: APIRequestContext, acct: Account, storyIds: string[] = []): Promise<{ appId: string; eventId: string; url: string }> {
  const app = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/me/applications", { employer: "Synthetic Hospital", role_title: "Ward nurse" });
  const ev = (await api<{ events: { id: string }[] }>(request, acct.auth, "post", `/api/v1/me/applications/${app.id}/events`, {
    title: "Panel interview", on_date: iso(new Date(Date.now() + 10 * 86_400_000)),
  })).events[0]!;
  await api(request, acct.auth, "put", `/api/v1/me/applications/${app.id}/events/${ev.id}/kit`, { story_ids: storyIds });
  return { appId: app.id, eventId: ev.id, url: `/applications/${app.id}/events/${ev.id}/kit` };
}

test("disputed advice: the accepted improvement stays, labelled, and the learner keeps it", async ({ page, request }) => {
  const s = await seeded(request, "br-dispute");
  await accept(request, s);
  const [baseline] = await api<{ id: string }[]>(request, s.acct.auth, "get", `/api/v1/careers/${TRACK}/questions/${BASELINE_Q}/answers`);
  await signIn(page, s.acct.email);

  await page.goto(`/careers/${TRACK}/questions/${BASELINE_Q}?answer=${baseline!.id}`);
  await page.getByText("Your reflection, flags and checking again").click();
  await page.getByRole("button", { name: `Flag “${IMPROVEMENT}”` }).click();
  await page.getByRole("radio", { name: "I disagree" }).check();
  await page.getByRole("button", { name: "Save flag" }).click();
  await expect(page.getByText(/this point doesn't shape your plan until you count it again/)).toBeVisible();

  await page.goto("/plan");
  const section = page.getByRole("region", { name: "Improvements you accepted (1)" });
  await expect(section).toContainText(IMPROVEMENT);
  await expect(section).toContainText("It stays as it is; it's yours to keep, move or mark done.");
});

test("an incompatible comparison: a retry too short to score is compared by what was written, not by numbers", async ({ page, request }) => {
  const s = await seeded(request, "br-compare");
  await signIn(page, s.acct.email);
  await page.goto(`/interviews/${s.interviewId}/retry/0`);
  await page.getByLabel("Your new answer").fill("I would check it again.");
  await page.getByRole("button", { name: "Get feedback and compare" }).click();
  await expect(page.getByText(/too short to score: compare what you wrote, not the numbers/).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Latest retry/ })).not.toHaveText(/\([+−-]\d+\)/);
});

test("stale evidence: the kit says the story changed since it was chosen, and keeps what it prepared", async ({ page, request }) => {
  const s = await seeded(request, "br-stale");
  const story = await api<{ id: string }>(request, s.acct.auth, "post", "/api/v1/me/stories", {
    title: "Two call lights", situation: "Two patients rang at once.", result: "Both were seen within five minutes.",
  });
  const kit = await kitWith(request, s.acct, [story.id]);
  await signIn(page, s.acct.email);
  await page.goto(`/stories/${story.id}`);
  await page.getByLabel("Result", { exact: true }).fill("Both were seen within five minutes and the family was told.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText(/^Saved as version \d+\.$/)).toBeVisible();

  await page.goto(kit.url);
  const review = page.locator(".freshness").filter({ hasText: "Two call lights" });
  await expect(review).toContainText("The story changed since you chose it for this kit (version 1, now 2). Review whether it still fits.");
  await expect(page.getByRole("article", { name: "Your interview pack" })).toContainText("Two call lights (version 1; the story has changed since)");
});

test("a deletion race: a scope that grew after the preview is refused, and nothing is deleted", async ({ page, request }) => {
  const s = await seeded(request, "br-delete");
  const kit = await kitWith(request, s.acct);
  await signIn(page, s.acct.email);
  await page.goto(`/applications/${kit.appId}`);
  await page.getByRole("button", { name: "Delete…" }).click();
  const group = page.getByRole("group", { name: "What this will do" });
  await expect(group.getByRole("button", { name: "Delete this application, its 1 event and 1 kit" })).toBeVisible();
  // Another tab adds an event after the preview.
  await api(request, s.acct.auth, "post", `/api/v1/me/applications/${kit.appId}/events`, { title: "Final interview", on_date: iso(new Date(Date.now() + 20 * 86_400_000)) });
  await group.getByRole("button", { name: "Delete this application, its 1 event and 1 kit" }).click();
  await expect(group).toContainText("What this affects changed since you looked. Nothing was done: check the list again.");
  expect((await request.get(`${API_URL}/api/v1/me/applications/${kit.appId}`, { headers: s.acct.auth })).status()).toBe(200);
});

test("a lost response: accepting again after a lost reply finds the same action", async ({ page, request }) => {
  const s = await seeded(request, "br-lost");
  await signIn(page, s.acct.email);
  await page.goto(`/interviews/${s.interviewId}`);
  // The first accept reaches the server and is saved; its reply never reaches the page.
  await page.route("**/api/v1/me/actions", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fetch();
    await route.abort("failed");
  }, { times: 1 });
  const item = page.getByRole("listitem").filter({ has: page.getByRole("button", { name: `Accept as an action: ${IMPROVEMENT}` }) });
  await item.getByRole("button", { name: `Accept as an action: ${IMPROVEMENT}` }).click();
  await expect(page.getByText(/Accepted as an action\./)).toHaveCount(0);
  await expect(item.getByRole("button", { name: `Accept as an action: ${IMPROVEMENT}` })).toBeEnabled();
  await item.getByRole("button", { name: `Accept as an action: ${IMPROVEMENT}` }).click();
  await expect(page.getByText(/Accepted as an action\./).first()).toBeVisible();
  expect(await api<unknown[]>(request, s.acct.auth, "get", "/api/v1/me/actions")).toHaveLength(1);
});

test("another account: the kit, the interview and the action are not found, the same as missing ones", async ({ page, request }) => {
  const s = await seeded(request, "br-owner");
  const actionId = await accept(request, s);
  const kit = await kitWith(request, s.acct);
  const other = await newAccount(request, "br-stranger");
  await signIn(page, other.email);
  await page.goto(kit.url);
  await expect(page.getByRole("heading", { level: 1, name: "This interview kit isn't available" })).toBeVisible();
  await page.goto(`/interviews/${s.interviewId}`);
  await expect(page.getByText(/Interview not found|couldn't find|isn't available/i).first()).toBeVisible();
  for (const p of [`/api/v1/me/actions/${actionId}`, `/api/v1/targets/${s.targetId}`, `/api/v1/me/applications/${kit.appId}/events/${kit.eventId}/kit`]) {
    const theirs = await request.get(`${API_URL}${p}`, { headers: other.auth });
    expect(theirs.status(), p).toBe(404);
  }
});
