import { readFileSync } from "node:fs";

import type { APIRequestContext, Browser, BrowserContext, Page, TestInfo } from "@playwright/test";

import { expect, navTo } from "./fixtures";
import { ACCESS_LOG } from "./ports";
import { Recorder, api, iso, newAccount, signIn, signInApi, type Account, type JudgeVerdict } from "./preparation-journey";

/**
 * A software engineer's preparation journey, judged for real (Volume 13, prompt 10;
 * docs/PREPARATION_JOURNEY.md, "The software engineer's journey"), against the real API, the code
 * judge in its gVisor sandbox and the built-in coach: a target requirement → a hint whose preview
 * is what's sent → a coding baseline judged in the sandbox → its recorded help → an approved code
 * review (the request carries the preview's fingerprint and the code it showed) → a coding
 * interview's feedback → an accepted improvement → its calendar placement → a resubmission judged
 * in the sandbox, shown with its own verdict (coding submissions aren't compared) → the
 * interview-day kit. Each id is found again after a reload and a fresh sign-in, and a canary typed
 * by the learner is never in the API's log. The judge's verdicts are recorded as it gave them.
 *
 * It needs the real judge (E2E_JUDGE=1: Docker, gVisor and the sandbox image). Without it the specs
 * skip with that reason, and with E2E_JUDGE=1 but no ready judge the journey stops at its first
 * step, saying why: it never records a verdict nobody judged. Synthetic code and accounts only.
 */

export const SE_TRACK = "software-engineer";
export const PROBLEM = "two-sum";
export const PROBLEM_TITLE = "Two Sum";
export const REQ_DSA = "Strong knowledge of data structures and algorithms";
export const SE_JD = `Software Engineer - Payments Platform
Requirements:
- ${REQ_DSA}
- Experience writing tests for production code
Responsibilities:
- Review teammates' code and give clear feedback
- Design and build reliable APIs`;
/** Right for two of the three public tests (the first pair happens to be at 0 and 1). */
export const BASELINE = `class Solution {
    public int[] twoSum(int[] nums, int target) {
        return new int[] {0, 1};
    }
}`;
/** A synthetic marker typed by the learner; it must never reach a log, a trace or an email. */
export const SE_CANARY = "CANARY-engineer-4c1d8-not-a-real-secret";
export const RESUBMISSION = `import java.util.HashMap;
import java.util.Map;

class Solution {
    // One pass: remember each value's index, look up the complement first. (${SE_CANARY})
    public int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> seen = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            Integer j = seen.get(target - nums[i]);
            if (j != null) return new int[] {j, i};
            seen.put(nums[i], i);
        }
        throw new IllegalArgumentException("no pair");
    }
}`;
/** A coding interview's improvement lists submissions of its problem (Volume 14, prompt 2). */
export const CODE_NOTE = "Submissions of the interview's problem since you accepted this, found by a stored link (the interview names its problem).";
export const JUDGE_NEEDED = "needs the real judge: set E2E_JUDGE=1 (Docker, gVisor and the sandbox image). Without it this journey stops rather than record a verdict nobody judged";

interface Result {
  passed_count: number; total_count: number; hidden_passed: number; hidden_total: number;
  runtime_ms: number | null; public_results: { runtime_ms?: number | null }[];
}
export interface Sub {
  id: string; mode: string; status: string; status_detail: string | null; is_terminal: boolean;
  created_at: string; updated_at: string; result: Result | null; conditions: { labels: string[] } | null;
  compared?: { previous: { id: string; status: string }; comparison: { outcome: string; explanation: string } } | null;
}
interface Preview { context_fingerprint: string; items: { key: string; label: string; text: string }[]; recipient_kind: string }
interface Action { id: string; title: string; source: Record<string, unknown>; occurrences: { id: string }[] }

// --- helpers -------------------------------------------------------------------------------------

/** Replaces the editor's code as a person pasting it would. */
export async function paste(page: Page, code: string): Promise<void> {
  await page.locator(".monaco-editor").first().click();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.press("Delete");
  await page.evaluate((text) => navigator.clipboard.writeText(text), code);
  await page.keyboard.press("ControlOrMeta+V");
}

/** The judge must be on and ready (`/capabilities`); otherwise this says why, and the journey stops. */
export async function judgeReady(request: APIRequestContext, acct: Account, rec: Recorder): Promise<void> {
  const caps = await api<{ ai_provider: string; execution_enabled: boolean; execution?: { state: string; message: string; submit_mode: string } }>(
    request, acct.auth, "get", "/api/v1/capabilities");
  rec.facts.ai_provider = caps.ai_provider;
  rec.facts.code_execution = caps.execution_enabled;
  rec.facts.judge_state = caps.execution?.state ?? null;
  if (!caps.execution_enabled || caps.execution?.state !== "ready") {
    rec.facts.stopped = `the sandbox isn't available here (${caps.execution?.state ?? "execution off"}: ${caps.execution?.message ?? "no judge configured"})`;
    throw new Error(`The real judge isn't available (${caps.execution?.state ?? "execution off"}): this journey ${JUDGE_NEEDED}.`);
  }
}

/** Submits the editor's code with the Submit button and waits for the sandbox's verdict on screen. */
export async function submitAndJudge(page: Page, request: APIRequestContext, acct: Account, verdictText: string): Promise<{ sub: Sub; seenMs: number }> {
  const created = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/submissions" && r.request().method() === "POST");
  const t0 = Date.now();
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  const res = await created;
  expect(res.status(), "the submission is accepted for judging").toBe(202);
  const { id } = (await res.json()) as { id: string };
  await expect(page.getByText(verdictText)).toBeVisible({ timeout: 120_000 });
  const seenMs = Date.now() - t0;
  const sub = await api<Sub>(request, acct.auth, "get", `/api/v1/submissions/${id}`);
  expect(sub.is_terminal).toBe(true);
  return { sub, seenMs };
}

export function verdict(step: string, sub: Sub, seenMs: number | null): JudgeVerdict {
  const r = sub.result;
  return {
    step, submission_id: sub.id, mode: sub.mode, status: sub.status, status_detail: sub.status_detail,
    passed_count: r?.passed_count ?? null, total_count: r?.total_count ?? null,
    hidden_passed: r?.hidden_passed ?? null, hidden_total: r?.hidden_total ?? null,
    runtime_ms: r?.runtime_ms ?? null, public_runtime_ms: (r?.public_results ?? []).map((p) => p.runtime_ms ?? null),
    queued_to_verdict_ms: new Date(sub.updated_at).getTime() - new Date(sub.created_at).getTime(),
    seen_after_ms: seenMs,
  };
}

/** The verdict's numbers as the results panel shows them. */
export async function expectResultShown(page: Page, sub: Sub): Promise<void> {
  const r = sub.result!;
  const panel = page.getByRole("region", { name: "Submission results" });
  await expect(panel.getByText(`${r.passed_count}/${r.total_count} tests passed`)).toBeVisible();
  if (r.hidden_total > 0) await expect(panel.getByText(`hidden: ${r.hidden_passed}/${r.hidden_total}`)).toBeVisible();
  if (r.runtime_ms !== null) await expect(panel.getByText(`${r.runtime_ms} ms`, { exact: true })).toBeVisible();
}

const usedToday = async (request: APIRequestContext, acct: Account) =>
  (await api<{ used_today: number }>(request, acct.auth, "get", "/api/v1/ai/usage")).used_today;

/** The coach's preview (what it will read) and the request the page sent for it: the same material. */
async function sentMatchesPreview(previewText: string, preview: Preview, sent: Record<string, unknown>, code: string): Promise<void> {
  const shownCode = preview.items.find((i) => i.key === "code")?.text;
  expect(sent.approved_context, "the request carries the preview's fingerprint").toBe(preview.context_fingerprint);
  expect(sent.source_code, "the request sends the code that was checked").toBe(code);
  expect(shownCode, "the preview shows that code").toBe(code);
  expect(previewText.trim(), "what's on screen is the preview's text").toBe(shownCode!.trim());
}

// --- the journey -------------------------------------------------------------------------------------

export async function engineerJourney(page: Page, context: BrowserContext, browser: Browser, request: APIRequestContext, info: TestInfo): Promise<Recorder> {
  const rec = new Recorder(info, "engineer-journey");
  try {
    await run(rec, page, context, browser, request);
  } finally {
    rec.write(true);
  }
  return rec;
}

async function run(rec: Recorder, page: Page, context: BrowserContext, browser: Browser, request: APIRequestContext) {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const acct = await newAccount(request, "engineer", SE_TRACK);
  const first = new Date(Date.now() + 86_400_000);
  let targetId = "";
  let baselineId = "";
  let resubmissionId = "";
  let interviewId = "";
  let actionId = "";
  let improvement = "";
  let kitUrl = "";

  await rec.step("The judge is ready", async (check) => {
    await judgeReady(request, acct, rec);
    check(`/capabilities: code execution on, the judge "ready" (submissions are judged in the sandbox), the coach "${rec.facts.ai_provider}"`);
  });

  await signIn(page, acct.email);

  await rec.step("A target requirement", async (check) => {
    await page.goto("/targets");
    await page.getByRole("button", { name: "Add a target role" }).first().click();
    await page.getByLabel("Role title").fill("Backend engineer");
    await page.getByLabel("Job description").fill(SE_JD);
    await page.getByRole("button", { name: "Find requirements" }).click();
    await expect(page).toHaveURL(/\/targets\/[0-9a-f-]+$/);
    targetId = page.url().split("/").pop()!;
    const req = page.getByRole("article", { name: REQ_DSA });
    await expect(req).toContainText("Limited evidence: not practised yet");
    const link = req.getByRole("link", { name: `Problem: ${PROBLEM_TITLE}` });
    await expect(link).toBeVisible();
    await expect(req).toContainText("Coding practice for arrays, hash maps");
    check(`"${REQ_DSA}" is a requirement, not practised yet, offering "Problem: ${PROBLEM_TITLE} · Coding practice for arrays, hash maps"`);
    const t = await api<{ requirement_list: { id: string; text: string }[] }>(request, acct.auth, "get", `/api/v1/targets/${targetId}`);
    rec.ids.target = targetId;
    rec.ids.requirements = t.requirement_list.map((r) => r.id);
    rec.ids.requirement = t.requirement_list.find((r) => r.text === REQ_DSA)!.id;
    await link.click();
    await expect(page).toHaveURL(new RegExp(`/problems/${PROBLEM}$`));
    await expect(page.locator(".monaco-editor")).toBeVisible();
    check(`the link opens the ${PROBLEM_TITLE} workspace`);
  });

  await rec.step("Approved coach context: a hint", async (check) => {
    await paste(page, BASELINE);
    const coach = page.getByRole("region", { name: "AI coach" });
    const before = await usedToday(request, acct);
    const previewed = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/ai/hint/preview");
    await coach.getByRole("button", { name: "Get a hint" }).click();
    const panel = coach.locator("section").filter({ has: page.getByRole("heading", { name: "What the coach will read" }) });
    await expect(panel.getByText("Level 1 of 4: Nudge.")).toBeVisible();
    await expect(panel.getByText(/The built-in coach, on CodeCoach's own server: nothing leaves it/)).toBeVisible();
    const preview = (await (await previewed).json()) as Preview;
    const shown = (await panel.getByLabel("Exactly what's sent: Your code").textContent()) ?? "";
    expect(await usedToday(request, acct)).toBe(before);
    check("checking shows the code the coach will read, as level 1 (nudge), from the built-in coach; checking used nothing");
    const sending = page.waitForRequest((r) => new URL(r.url()).pathname === "/api/v1/ai/hint" && r.method() === "POST");
    await panel.getByRole("button", { name: "Ask for the level 1 hint" }).click();
    await sentMatchesPreview(shown, preview, (await sending).postDataJSON() as Record<string, unknown>, BASELINE);
    await expect(coach.getByText("Level 1 · Nudge")).toBeVisible();
    expect(await usedToday(request, acct)).toBe(before + 1);
    check("the request carried the preview's fingerprint and the code it showed; the level 1 hint was shown and one request used");
  }, ["built-in coach"]);

  await rec.step("A coding baseline, judged for real", async (check) => {
    const { sub, seenMs } = await submitAndJudge(page, request, acct, "Some tests failed. Check the cases below.");
    expect(sub.status).toBe("FAILED");
    await expectResultShown(page, sub);
    baselineId = sub.id;
    rec.ids.baseline_submission = sub.id;
    rec.judged.push(verdict("A coding baseline, judged for real", sub, seenMs));
    const r = sub.result!;
    check(`judged in the sandbox: ${sub.status}, ${r.passed_count}/${r.total_count} tests passed (hidden ${r.hidden_passed}/${r.hidden_total}), ${r.runtime_ms ?? "no"} ms in the method, as the page shows`);
  }, ["real judge"]);

  await rec.step("Its recorded help", async (check) => {
    await page.goto(`/history/submissions/${baselineId}`);
    const help = page.locator(".attempt-conditions");
    await expect(help).toContainText("In-app help before this attempt: Hint shown");
    await expect(help).toContainText("Hint shown: Level 1 hint (nudge)");
    const sub = await api<Sub>(request, acct.auth, "get", `/api/v1/submissions/${baselineId}`);
    expect(sub.conditions?.labels).toEqual(["Hint shown"]);
    check(`the baseline says "In-app help before this attempt: Hint shown" with "Level 1 hint (nudge)", the hint asked for before it`);
  });

  await rec.step("An approved code review", async (check) => {
    await page.goto(`/problems/${PROBLEM}`);
    await expect(page.locator(".monaco-editor")).toBeVisible();
    await page.getByRole("tab", { name: "Code review" }).click();
    const before = await usedToday(request, acct);
    const previewed = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/ai/review/preview");
    await page.getByRole("button", { name: "Review my code" }).click();
    const panel = page.locator("section").filter({ has: page.getByRole("heading", { name: "What the coach will read" }) });
    await expect(panel.getByText(/The built-in coach, on CodeCoach's own server: nothing leaves it/)).toBeVisible();
    const shown = (await panel.getByLabel("Exactly what's sent: Your code").textContent()) ?? "";
    const preview = (await (await previewed).json()) as Preview;
    rec.facts.review_sent = preview.items.map((i) => i.label).join("; ");
    check(`the preview lists what the coach will read: ${rec.facts.review_sent}`);
    const sending = page.waitForRequest((r) => new URL(r.url()).pathname === "/api/v1/ai/review" && r.method() === "POST");
    const answered = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/ai/review" && r.request().method() === "POST");
    await panel.getByRole("button", { name: "Send for review" }).click();
    await sentMatchesPreview(shown, preview, (await sending).postDataJSON() as Record<string, unknown>, BASELINE);
    expect((await answered).status()).toBe(200);
    await expect(page.getByText("What's working")).toBeVisible();
    expect(await usedToday(request, acct)).toBe(before + 1);
    check("sent as previewed (the preview's fingerprint and the code it showed), answered by the built-in coach; one request used");
  }, ["built-in coach"]);

  await rec.step("Feedback review: a coding interview", async (check) => {
    await navTo(page, "Mock interview");
    await page.getByLabel("Problem", { exact: true }).selectOption(PROBLEM);
    await page.getByText("15 min").click();
    await page.getByRole("button", { name: "Start interview" }).click();
    await expect(page).toHaveURL(/\/interviews\/[0-9a-f-]+$/);
    interviewId = page.url().split("/").pop()!;
    rec.ids.interview = interviewId;
    await expect(page.locator(".monaco-editor")).toBeVisible();
    await page.getByLabel("Your answer").fill("I'd keep a hash map from each value to its index and look up the complement in one pass.");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.getByLabel("Interviewer is typing")).toHaveCount(0);
    await page.getByRole("button", { name: "Finish & get feedback" }).click();
    await expect(page.getByRole("heading", { name: "Interview feedback" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Work on next" })).toBeVisible();
    const review = await api<{ improvements: { key: string; title: string }[] }>(request, acct.auth, "get", `/api/v1/interviews/${interviewId}/review`);
    expect(review.improvements.length).toBeGreaterThan(0);
    improvement = review.improvements[0]!.title;
    rec.facts.improvements = review.improvements.map((i) => i.title).join("; ");
    rec.facts.improvement = improvement;
    await expect(page.getByRole("button", { name: `Accept as an action: ${improvement}` })).toBeVisible();
    check(`the interview's feedback lists "Work on next": ${rec.facts.improvements} (the built-in interviewer's rubric)`);
  }, ["built-in coach"]);

  await rec.step("An accepted improvement", async (check) => {
    const item = page.getByRole("listitem").filter({ has: page.getByRole("button", { name: `Accept as an action: ${improvement}` }) });
    await item.getByRole("checkbox", { name: "Every week" }).check();
    await item.getByRole("button", { name: `Accept as an action: ${improvement}` }).click();
    await expect(page.getByText(/Accepted as an action\./).first()).toBeVisible();
    const actions = await api<Action[]>(request, acct.auth, "get", "/api/v1/me/actions");
    expect(actions).toHaveLength(1);
    actionId = actions[0]!.id;
    rec.ids.action = actionId;
    expect(actions[0]!.source.interview_id).toBe(interviewId);
    check(`"${improvement}" is accepted as a weekly action, from this interview`);
  });

  await rec.step("Its calendar placement", async (check) => {
    await page.goto("/plan");
    const section = page.getByRole("region", { name: "Improvements you accepted (1)" });
    await section.getByRole("button", { name: "Add weeks to your schedule" }).click();
    await section.getByLabel("First week, on").fill(iso(first));
    await section.getByLabel("For how many weeks").selectOption("2");
    await section.getByRole("button", { name: "Add to schedule" }).click();
    await expect(section.getByRole("checkbox", { name: /^Week of/ })).toHaveCount(2);
    check("the plan schedules two weeks of it");
    await page.goto(`/schedule?week=${iso(first)}`);
    await expect(page.getByRole("button", { name: `Mark done: ${improvement}` }).first()).toBeVisible();
    check("the schedule shows it in the first week, not yet done");
    const a = await api<Action>(request, acct.auth, "get", `/api/v1/me/actions/${actionId}`);
    expect(a.occurrences).toHaveLength(2);
    rec.ids.occurrences = a.occurrences.map((o) => o.id);
  });

  await rec.step("A resubmission, judged for real", async (check) => {
    await page.goto(`/problems/${PROBLEM}`);
    await expect(page.locator(".monaco-editor")).toBeVisible();
    await paste(page, RESUBMISSION);
    const { sub, seenMs } = await submitAndJudge(page, request, acct, "All tests passed. Nice work.");
    expect(sub.status).toBe("PASSED");
    await expectResultShown(page, sub);
    resubmissionId = sub.id;
    rec.ids.resubmission = sub.id;
    rec.judged.push(verdict("A resubmission, judged for real", sub, seenMs));
    const r = sub.result!;
    check(`judged in the sandbox: ${sub.status}, ${r.passed_count}/${r.total_count} tests passed (hidden ${r.hidden_passed}/${r.hidden_total}), ${r.runtime_ms ?? "no"} ms in the method`);
    expect(sub.conditions?.labels).toEqual(["No in-app help recorded"]);
    check(`its help is its own: "No in-app help recorded" (the hint belonged to the attempt after it)`);

    // Compared with the baseline by the one comparison rule (docs/COMPARING_ATTEMPTS.md, "Coding
    // submissions"): the hint came before the baseline only, so the help differed. Both verdicts
    // stay as judged; nothing says the second improved on the first.
    const c = sub.compared!;
    expect(c.previous.id).toBe(baselineId);
    const box = page.getByRole("region", { name: "Compared with your previous submission" });
    await expect(box).toContainText(c.comparison.explanation);
    await expect(box).not.toContainText(/improv|better/i);
    rec.facts.comparison_outcome = c.comparison.outcome;
    rec.facts.comparison = c.comparison.explanation;
    check(`compared with the baseline under the result: "${c.comparison.explanation}"`);
    await page.goto("/history?type=code_submission");
    const rows = page.getByRole("listitem").filter({ hasText: PROBLEM_TITLE });
    await expect(rows).toHaveCount(2);
    await expect(rows.filter({ hasText: "In-app help: Hint shown" })).toHaveCount(1);
    await expect(rows.filter({ hasText: "In-app help: No in-app help recorded" })).toHaveCount(1);
    await expect(rows.filter({ hasText: "with the one before" })).toHaveCount(1);
    check("History lists both with their own help and the comparison on the later one");
    // The improvement from the coding interview lists it: a submission of the interview's problem
    // made since it was accepted, with its verdict and comparison. Nothing is ticked.
    await page.goto("/plan");
    const accepted = page.getByRole("region", { name: "Improvements you accepted (1)" });
    await accepted.getByText("Related practice since you accepted it (1)").click();
    const related = accepted.locator(".related-practice");
    await expect(related.getByRole("link", { name: `Submission: ${PROBLEM_TITLE}` })).toHaveAttribute("href", `/history/submissions/${sub.id}`);
    await expect(related).toContainText(`Passed ${r.passed_count} of ${r.total_count} tests passed`);
    await expect(related).toContainText(CODE_NOTE);
    check(`the improvement's related practice lists the resubmission ("Submission: ${PROBLEM_TITLE}", passed), not ticked`);
    const t = await api<{ requirement_list: { text: string; coverage: { label: string } }[] }>(request, acct.auth, "get", `/api/v1/targets/${targetId}`);
    const coverage = t.requirement_list.find((x) => x.text === REQ_DSA)!.coverage.label;
    rec.facts.requirement_coverage = coverage;
    await page.goto(`/targets/${targetId}`);
    await expect(page.getByRole("article", { name: REQ_DSA })).toContainText(coverage);
    const latest = page.getByRole("list", { name: `Your latest submissions for ${REQ_DSA}` });
    await expect(latest.getByRole("listitem")).toHaveCount(2);
    await expect(latest.getByRole("listitem").first()).toContainText("Passed");
    check(`the requirement now reads "${coverage}" and lists both submissions, newest first, with their verdicts`);
  }, ["real judge"]);

  await rec.step("Final preparation material", async (check) => {
    await page.goto("/applications");
    await page.getByRole("button", { name: "Add an application" }).click();
    const form = page.getByRole("form", { name: "New application" });
    await form.getByLabel("Role title").fill("Backend engineer");
    await form.getByLabel("Employer").fill("Synthetic Payments");
    await form.getByRole("button", { name: "Add application" }).click();
    await page.getByRole("link", { name: "Backend engineer" }).click();
    await expect(page).toHaveURL(/\/applications\/[0-9a-f-]+$/);
    rec.ids.application = page.url().split("/").pop()!;
    await page.getByRole("button", { name: "Add an event" }).click();
    const ev = page.getByRole("form", { name: "New event" });
    await ev.getByLabel("What").fill("Technical interview");
    await ev.getByLabel(/^Date/).fill(iso(new Date(Date.now() + 10 * 86_400_000)));
    await ev.getByRole("button", { name: "Add event" }).click();
    await page.getByRole("link", { name: "Interview-day kit" }).click();
    await expect(page).toHaveURL(/\/kit$/);
    await expect(page.getByRole("button", { name: "Save kit" })).toBeVisible();
    kitUrl = new URL(page.url()).pathname;
    rec.ids.event = kitUrl.split("/")[4]!;
    await page.getByLabel("Add an improvement you accepted").selectOption({ label: improvement });
    await page.getByRole("button", { name: "Add to checklist" }).click();
    await page.getByRole("textbox", { name: "Private notes" }).fill(`Bring the whiteboard pens (${SE_CANARY}).`); // open on a wide screen
    await page.getByRole("button", { name: "Save kit" }).click();
    await expect(page.getByText("Saved.")).toBeVisible();
    await page.reload();
    await expect(page.getByText(`${improvement} · 0 of 2 weeks done`)).toBeVisible();
    check(`the kit's checklist shows "${improvement} · 0 of 2 weeks done", read from the same action`);
    const pack = page.getByRole("article", { name: "Your interview pack" });
    await expect(pack).toContainText(improvement);
    check("the printable pack lists the accepted improvement");
  });

  await rec.step("Found again: reload and a fresh sign-in", async (check) => {
    await page.reload();
    await expect(page.getByText(`${improvement} · 0 of 2 weeks done`)).toBeVisible();
    check("after a reload the kit still reads the action");

    const device = await browser.newContext();
    const fresh = await device.newPage();
    await signIn(fresh, acct.email);
    await fresh.goto(`/history/submissions/${baselineId}`);
    await expect(fresh.locator(".attempt-conditions")).toContainText("In-app help before this attempt: Hint shown");
    await expect(fresh.getByRole("heading", { name: "Result" }).locator("..")).toContainText(`${rec.judged[0]!.passed_count} of ${rec.judged[0]!.total_count} tests passed`);
    await fresh.goto(`/history/submissions/${resubmissionId}`);
    await expect(fresh.getByRole("heading", { name: "Result" }).locator("..")).toContainText(`${rec.judged[1]!.passed_count} of ${rec.judged[1]!.total_count} tests passed`);
    await fresh.goto(kitUrl);
    await expect(fresh.getByText(`${improvement} · 0 of 2 weeks done`)).toBeVisible();
    await device.close();
    check("a fresh sign-in on another browser finds both submissions with their verdicts and the baseline's hint, and the kit");

    const auth = await signInApi(request, acct.email);
    const t = await api<{ requirement_list: { id: string }[] }>(request, auth, "get", `/api/v1/targets/${targetId}`);
    expect(t.requirement_list.map((r) => r.id)).toEqual(rec.ids.requirements);
    for (const [i, id] of [baselineId, resubmissionId].entries()) {
      const s = await api<Sub>(request, auth, "get", `/api/v1/submissions/${id}`);
      expect([s.status, s.result?.passed_count, s.result?.hidden_passed]).toEqual([rec.judged[i]!.status, rec.judged[i]!.passed_count, rec.judged[i]!.hidden_passed]);
    }
    const a = await api<Action>(request, auth, "get", `/api/v1/me/actions/${actionId}`);
    expect(a.source.interview_id).toBe(interviewId);
    expect(a.occurrences.map((o) => o.id)).toEqual(rec.ids.occurrences);
    const review = await api<{ improvements: { title: string; action_id: string | null }[] }>(request, auth, "get", `/api/v1/interviews/${interviewId}/review`);
    expect(review.improvements.find((i) => i.title === improvement)?.action_id).toBe(actionId);
    const kit = await api<{ checklist: { action_id?: string | null }[] }>(request, auth, "get", `/api/v1/me/applications/${rec.ids.application}/events/${rec.ids.event}/kit`);
    expect(kit.checklist.map((c) => c.action_id).filter(Boolean)).toEqual([actionId]);
    check("by the API with a new token: the target's requirement ids, both submissions with the same verdicts, the action (from this interview, its two occurrences), the review's link to it and the kit's");
  });

  await rec.step("No secret in the logs", async (check) => {
    const log = readFileSync(ACCESS_LOG, "utf8");
    expect(log.length).toBeGreaterThan(0);
    expect(log).not.toContain(SE_CANARY);
    check("the API's access log for this run doesn't contain the canary typed into the code and the kit's notes");
  });
}
