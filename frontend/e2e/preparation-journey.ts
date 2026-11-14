import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import type { APIRequestContext, Browser, BrowserContext, Page, TestInfo } from "@playwright/test";

import { expect } from "./fixtures";
import { ACCESS_LOG, API_URL } from "./ports";

/**
 * One connected preparation journey (Volume 12, prompt 10; docs/PREPARATION_JOURNEY.md), against
 * the real API: a target requirement → a baseline attempt → its recorded assistance → feedback
 * review → an accepted improvement → its calendar placement → a related follow-up attempt → the
 * interview-day kit. Each step names the outcome the learner sees and records the ids it made;
 * at the end every id is looked up again after a reload, in a second tab and after a fresh
 * sign-in. Whatever the follow-up scores is recorded as it is. Synthetic accounts only.
 */

export const TRACK = "registered-nurse";
export const REQ_ASSESS = "Perform patient assessment and triage for incoming patients";
export const REQ_MEDS = "Administer medications and monitor patient responses";
export const JD = `Registered Nurse - Medical Ward
Requirements:
- Patient assessment and triage
- Infection control
- Patient education
Responsibilities:
- ${REQ_ASSESS}
- ${REQ_MEDS}`;
/** The targeted session this posting gives (worked out by the server; checked, not assumed). */
export const SESSION = ["e-accuracy-0", "e-accuracy-4", "e-accuracy-3"];
export const BASELINE_Q = "e-accuracy-0"; // "Checking your patient assessment work"
export const FOLLOW_UP_Q = "e-accuracy-1"; // its reviewed follow-up: "Checking your medication administration work"
export const FOLLOW_UP_TITLE = "Checking your medication administration work";
export const IMPROVEMENT = "Explains why it matters"; // missed in all three answers below
export const STRONG =
  "Last winter, while I was working nights, a patient's oxygen dropped during my 2 a.m. patient assessment. " +
  "I was responsible for five patients, so I moved fast. I checked his vital signs again and started oxygen " +
  "per protocol. I called the rapid response team and asked the charge nurse to cover my other patients. I " +
  "updated the doctor and documented everything. As a result, he was stable within 30 minutes, and I learned to escalate early.";
export const MIDDLING =
  "Last winter on a busy ward I noticed a patient's breathing change during my night round. I checked his " +
  "observations, raised the bed, started oxygen as prescribed and called the doctor. Within the hour his saturation " +
  "was back to 96%, and I learned to escalate early rather than wait to be certain.";
/** The retry adds the missing point. */
export const IMPROVED = `${STRONG} It matters because a change missed on a night round can mean a patient gets worse before anyone acts.`;
/** A secret-shaped string typed by the learner; it must never reach a log, a trace or an email. */
export const CANARY = "CANARY-journey-7f3a9-not-a-real-secret";
const PASSWORD = "CorrectHorse42";

export const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

// --- the record ------------------------------------------------------------------------------------

export type StepOutcome = "passed" | "failed" | "absent";
interface Step {
  n: number;
  name: string;
  outcome: StepOutcome;
  checks: string[];
  note?: string;
}

/** What the journey did, step by step, written to test-results/journey/ for the journey record. */
export class Recorder {
  steps: Step[] = [];
  ids: Record<string, string | string[] | number | null> = {};
  facts: Record<string, string | number | boolean | null> = {};
  private current: Step | null = null;

  constructor(private info: TestInfo, private kind: string) {}

  async step(name: string, run: (check: (what: string) => void) => Promise<void>): Promise<void> {
    const s: Step = { n: this.steps.length + 1, name, outcome: "failed", checks: [] };
    this.steps.push(s);
    this.current = s;
    await run((what) => s.checks.push(what));
    s.outcome = "passed";
    this.current = null;
  }

  absent(name: string, note: string) {
    this.steps.push({ n: this.steps.length + 1, name, outcome: "absent", checks: [], note });
  }

  write(): void {
    const dir = path.join("test-results", "journey");
    mkdirSync(dir, { recursive: true });
    const file = path.join(dir, `${this.kind}-${this.info.project.name}-r${this.info.repeatEachIndex}.json`);
    writeFileSync(file, JSON.stringify({
      kind: this.kind, project: this.info.project.name, repeat: this.info.repeatEachIndex,
      finished: this.current === null && this.steps.every((s) => s.outcome !== "failed"),
      steps: this.steps, ids: this.ids, facts: this.facts,
    }, null, 2));
  }
}

// --- accounts ----------------------------------------------------------------------------------------

export interface Account { email: string; auth: Record<string, string> }

export async function newAccount(request: APIRequestContext, prefix: string): Promise<Account> {
  const email = `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD, career_track: TRACK } });
  expect(reg.status(), "register").toBe(201);
  return { email, auth: { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` } };
}

/** A fresh API sign-in: a new token, as a second device would get. */
export async function signInApi(request: APIRequestContext, email: string): Promise<Record<string, string>> {
  const r = await request.post(`${API_URL}/api/v1/auth/login`, { data: { email, password: PASSWORD } });
  expect(r.status(), "login").toBe(200);
  return { Authorization: `Bearer ${((await r.json()) as { access_token: string }).access_token}` };
}

export async function signIn(page: Page, email: string): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

export async function api<T>(request: APIRequestContext, auth: Record<string, string>, method: "get" | "post" | "put" | "patch", p: string, data?: unknown): Promise<T> {
  const r = await request[method](`${API_URL}${p}`, { headers: auth, ...(data === undefined ? {} : { data }) });
  expect(r.ok(), `${method.toUpperCase()} ${p}: ${r.status()} ${await r.text()}`).toBe(true);
  return (await r.json()) as T;
}

/** Answers the round on screen; an interviewer's follow-up, if one comes, is skipped. */
async function answerRound(page: Page, answers: string[]): Promise<void> {
  for (const [i, text] of answers.entries()) {
    await expect(page.getByText(new RegExp(`QUESTION ${i + 1} OF ${answers.length}`))).toBeVisible();
    await page.getByLabel("Your answer", { exact: true }).fill(text);
    await page.getByRole("button", { name: i + 1 === answers.length ? "Finish interview" : "Next question" }).click();
    if (i + 1 < answers.length) {
      const reply = page.getByLabel("Your reply");
      await expect(reply.or(page.getByText(new RegExp(`QUESTION ${i + 2} OF`)))).toBeVisible();
      if (await reply.isVisible()) await page.getByRole("button", { name: "Skip follow-up" }).click();
    }
  }
}

interface Action { id: string; title: string; source: Record<string, unknown>; occurrences: { id: string; on_date: string; completed_at: string | null }[] }
interface QAnswer { id: string; score: number; follows_up_answer_id?: string | null; conditions?: { labels: string[] } | null }

// --- the journey -------------------------------------------------------------------------------------

export async function journey(page: Page, context: BrowserContext, browser: Browser, request: APIRequestContext, info: TestInfo): Promise<Recorder> {
  const rec = new Recorder(info, "journey");
  try {
    await run(rec, page, context, browser, request);
  } finally {
    rec.write();
  }
  return rec;
}

async function run(rec: Recorder, page: Page, context: BrowserContext, browser: Browser, request: APIRequestContext) {
  const acct = await newAccount(request, "journey");
  const caps = await api<Record<string, unknown>>(request, acct.auth, "get", "/api/v1/capabilities");
  rec.facts.ai_provider = String(caps.ai_provider ?? "unknown");
  rec.facts.code_execution = Boolean(caps.execution_enabled);
  await signIn(page, acct.email);
  const first = new Date(Date.now() + 86_400_000);
  let targetId = "";
  let interviewId = "";
  let actionId = "";
  let storyId = "";
  let kitUrl = "";

  await rec.step("A target requirement", async (check) => {
    await page.goto("/targets");
    await page.getByRole("button", { name: "Add a target role" }).first().click();
    await page.getByLabel("Role title").fill("Ward nurse");
    await page.getByLabel("Job description").fill(JD);
    await page.getByRole("button", { name: "Find requirements" }).click();
    await expect(page).toHaveURL(/\/targets\/[0-9a-f-]+$/);
    targetId = page.url().split("/").pop()!;
    await expect(page.getByRole("article", { name: REQ_ASSESS })).toBeVisible();
    await expect(page.getByRole("article", { name: REQ_MEDS })).toBeVisible();
    check(`the workspace lists "${REQ_ASSESS}" and "${REQ_MEDS}" as requirements`);
    const t = await api<{ requirement_list: { id: string; text: string }[]; targeted_session: { round: { question_ids: string[] } } }>(request, acct.auth, "get", `/api/v1/targets/${targetId}`);
    expect(t.targeted_session.round.question_ids).toEqual(SESSION);
    check(`its short targeted session is ${SESSION.join(", ")} (patient assessment first)`);
    rec.ids.target = targetId;
    rec.ids.requirements = t.requirement_list.map((r) => r.id);
  });

  rec.absent("Approved coach context",
    "Not part of a registered nurse's path: only the code review shows and binds what the coach reads (docs/COACH_CONTEXT.md); " +
    "written answers, career interviews and story help send nothing to a coach, so there is nothing to approve. " +
    "Exercised on a software-engineer account by e2e/coach-context.spec.ts, not here.");

  await rec.step("A baseline attempt", async (check) => {
    await page.goto(`/targets/${targetId}`);
    await page.getByText("Short targeted session", { exact: true }).click();
    await page.getByRole("button", { name: "Start (3 questions, 10 min)" }).click();
    await expect(page).toHaveURL(/\/interviews\/[0-9a-f-]+/);
    interviewId = page.url().match(/\/interviews\/([0-9a-f-]+)/)![1]!;
    await answerRound(page, [STRONG, MIDDLING, STRONG]);
    await expect(page.getByRole("heading", { name: "Work on next" })).toBeVisible();
    check("the targeted session starts from the target and its three answers are saved");
    const answers = await api<QAnswer[]>(request, acct.auth, "get", `/api/v1/careers/${TRACK}/questions/${BASELINE_Q}/answers`);
    expect(answers).toHaveLength(1);
    rec.ids.interview = interviewId;
    rec.ids.baseline_answer = answers[0]!.id;
    rec.facts.baseline_score = answers[0]!.score;
    check(`the patient-assessment answer scored ${answers[0]!.score}/100`);
  });

  await rec.step("Its recorded assistance", async (check) => {
    await page.goto(`/careers/${TRACK}/questions/${BASELINE_Q}`);
    const past = page.locator(".card").filter({ has: page.getByRole("heading", { name: "Your past answers" }) });
    await expect(past).toContainText(`${rec.facts.baseline_score}/100`);
    await past.getByRole("button").first().click();
    await expect(page.getByText("In-app help before this attempt:")).toBeVisible();
    await expect(page.locator(".attempt-conditions")).toContainText("No in-app help recorded");
    check(`the baseline answer says "In-app help before this attempt: No in-app help recorded" (no lesson prepares this question, and no hint was shown)`);
  });

  await rec.step("Feedback review", async (check) => {
    await page.goto(`/interviews/${interviewId}`);
    await expect(page.getByRole("heading", { name: "Work on next" })).toBeVisible();
    const item = page.getByRole("listitem").filter({ has: page.getByRole("button", { name: `Accept as an action: ${IMPROVEMENT}` }) });
    await expect(item).toContainText("Missing in 3 of 3 answers.");
    check(`the replay's "Work on next" names "${IMPROVEMENT}", missing in 3 of 3 answers`);
  });

  await rec.step("An accepted improvement", async (check) => {
    const item = page.getByRole("listitem").filter({ has: page.getByRole("button", { name: `Accept as an action: ${IMPROVEMENT}` }) });
    await item.getByRole("checkbox", { name: "Every week" }).check();
    await item.getByRole("button", { name: `Accept as an action: ${IMPROVEMENT}` }).click();
    await expect(page.getByText(/Accepted as an action\./).first()).toBeVisible();
    check(`"${IMPROVEMENT}" is accepted as a weekly action`);
    const actions = await api<Action[]>(request, acct.auth, "get", "/api/v1/me/actions");
    expect(actions).toHaveLength(1);
    actionId = actions[0]!.id;
    rec.ids.action = actionId;
    await page.goto(`/targets/${targetId}`);
    await expect(page.getByText(`Accepted improvement “${IMPROVEMENT}”`).first()).toBeVisible();
    check("the target's requirement lists the accepted improvement");
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
    await expect(page.getByRole("button", { name: `Mark done: ${IMPROVEMENT}` }).first()).toBeVisible();
    check("the schedule shows it in the first week, not yet done");
    const a = await api<Action>(request, acct.auth, "get", `/api/v1/me/actions/${actionId}`);
    expect(a.occurrences).toHaveLength(2);
    rec.ids.occurrences = a.occurrences.map((o) => o.id);
  });

  await rec.step("A related follow-up attempt", async (check) => {
    // A second scored answer to the same question (a retry from the replay) is what makes the
    // reviewed follow-up appear (docs/FOLLOW_UPS.md).
    await page.goto(`/interviews/${interviewId}/retry/0`);
    await page.getByLabel("Your new answer").fill(IMPROVED);
    await page.getByRole("button", { name: "Get feedback and compare" }).click();
    await expect(page.getByRole("heading", { name: /^Latest retry · \d+\/100/ })).toBeVisible();
    await expect(page.getByText(/Partly comparable: the conditions differed/).first()).toBeVisible();
    check("the retry is compared with the interview answer and labelled partly comparable, because the conditions differed");
    const tries = await api<QAnswer[]>(request, acct.auth, "get", `/api/v1/careers/${TRACK}/questions/${BASELINE_Q}/answers`);
    expect(tries).toHaveLength(2);
    rec.ids.retry_answer = tries[0]!.id;
    rec.facts.retry_score = tries[0]!.score;

    await page.goto(`/careers/${TRACK}/questions/${BASELINE_Q}`);
    const heading = page.getByRole("heading", { name: "A related question" });
    await expect(heading).toBeVisible();
    const card = page.locator("section").filter({ has: heading });
    await expect(card).toContainText("Not previously attempted in this app.");
    check(`"A related question" offers "${FOLLOW_UP_TITLE}", not previously attempted`);
    await card.getByRole("link", { name: FOLLOW_UP_TITLE }).click();
    await expect(page).toHaveURL(new RegExp(`/questions/${FOLLOW_UP_Q}\\?followUpOf=`));
    await expect(page.getByText(/A follow-up to your answer to a related question/)).toBeVisible();
    await page.getByRole("textbox", { name: "Your answer" }).fill(MIDDLING);
    await page.getByRole("button", { name: "Get feedback" }).click();
    const feedback = page.getByRole("region", { name: "Feedback", exact: true });
    await expect(feedback.getByLabel(/^Score \d+ out of 100/)).toBeVisible();
    const followUps = await api<QAnswer[]>(request, acct.auth, "get", `/api/v1/careers/${TRACK}/questions/${FOLLOW_UP_Q}/answers`);
    expect(followUps).toHaveLength(1);
    const f = followUps[0]!;
    expect(f.follows_up_answer_id).toBe(rec.ids.retry_answer);
    rec.ids.follow_up_answer = f.id;
    rec.facts.follow_up_score = f.score;
    await expect(feedback.getByLabel(`Score ${f.score} out of 100`)).toBeVisible();
    check(`the follow-up is its own attempt, linked to the retry, scored ${f.score}/100 and shown as that`);
    // Whatever it scored is what's shown; nothing is combined or replaced (here it's lower).
    await page.goto(`/careers/${TRACK}/questions/${BASELINE_Q}`);
    const answered = page.getByRole("heading", { name: "Follow-ups you answered" }).locator("xpath=..");
    await expect(answered).toContainText(`${FOLLOW_UP_TITLE}: ${f.score}/100`);
    await expect(answered).toContainText("Scores aren't combined, and a result either way is more evidence, not a verdict.");
    await expect(answered).not.toContainText(/improv|average/i);
    check(`the first question lists the follow-up at ${f.score}/100 beside its own tries, not combined`);
    rec.facts.follow_up_lower_than_baseline = f.score < Number(rec.facts.baseline_score);
  });

  await rec.step("Final preparation material", async (check) => {
    // A story for the requirement (with the canary in it), then the kit for an interview.
    await page.goto(`/targets/${targetId}`);
    await page.getByRole("button", { name: "Add an example" }).click();
    await page.getByLabel("Short title").fill("Two call lights at once");
    await page.getByLabel("Situation (optional)").fill(`Two patients rang at once on a night shift (${CANARY}).`);
    await page.getByLabel("What you did (optional)").fill("I checked who was at higher risk first.");
    await page.getByLabel("Result (optional)").fill("Both were seen within five minutes.");
    await page.getByRole("checkbox", { name: REQ_ASSESS }).check();
    await page.getByRole("button", { name: "Save example" }).click();
    await page.getByRole("link", { name: "Open in your story bank" }).click();
    await expect(page).toHaveURL(/\/stories\/[0-9a-f-]+$/);
    storyId = page.url().split("/").pop()!;
    rec.ids.story = storyId;

    await page.goto("/applications");
    await page.getByRole("button", { name: "Add an application" }).click();
    const form = page.getByRole("form", { name: "New application" });
    await form.getByLabel("Role title").fill("Ward nurse");
    await form.getByLabel("Employer").fill("Synthetic Hospital");
    await form.getByRole("button", { name: "Add application" }).click();
    await page.getByRole("link", { name: "Ward nurse" }).click();
    await expect(page).toHaveURL(/\/applications\/[0-9a-f-]+$/);
    rec.ids.application = page.url().split("/").pop()!;
    await page.getByRole("button", { name: "Add an event" }).click();
    const ev = page.getByRole("form", { name: "New event" });
    await ev.getByLabel("What").fill("Panel interview");
    await ev.getByLabel(/^Date/).fill(iso(new Date(Date.now() + 10 * 86_400_000)));
    await ev.getByRole("button", { name: "Add event" }).click();
    await page.getByRole("link", { name: "Interview-day kit" }).click();
    await expect(page).toHaveURL(/\/kit$/);
    await expect(page.getByRole("button", { name: "Save kit" })).toBeVisible();
    kitUrl = new URL(page.url()).pathname;
    rec.ids.event = kitUrl.split("/")[4]!;
    await page.getByLabel("Add an improvement you accepted").selectOption({ label: IMPROVEMENT });
    await page.getByRole("button", { name: "Add to checklist" }).click();
    await page.getByRole("checkbox", { name: "Two call lights at once" }).check();
    await page.getByRole("button", { name: "Save kit" }).click();
    await expect(page.getByText("Saved.")).toBeVisible();
    await page.reload();
    await expect(page.getByText(`${IMPROVEMENT} · 0 of 2 weeks done`)).toBeVisible();
    check(`the kit's checklist shows the accepted improvement as "${IMPROVEMENT} · 0 of 2 weeks done", read from the same action`);
    const pack = page.getByRole("article", { name: "Your interview pack" });
    await expect(pack).toContainText(IMPROVEMENT);
    await expect(pack).toContainText("Two call lights at once");
    check("the printable pack lists the accepted improvement and the chosen story");
  });

  await rec.step("Found again: reload, a second tab and a fresh sign-in", async (check) => {
    await page.reload();
    await expect(page.getByText(`${IMPROVEMENT} · 0 of 2 weeks done`)).toBeVisible();
    check("after a reload the kit still reads the action");

    const second = await context.newPage();
    await second.goto("/plan");
    await expect(second.getByRole("region", { name: "Improvements you accepted (1)" }).getByRole("checkbox", { name: /^Week of/ })).toHaveCount(2);
    await second.goto(`/targets/${targetId}`);
    await expect(second.getByText(`Accepted improvement “${IMPROVEMENT}”`).first()).toBeVisible();
    await second.close();
    check("a second tab shows the same two weeks and the same requirement link");

    const device = await browser.newContext();
    const fresh = await device.newPage();
    await signIn(fresh, acct.email);
    await fresh.goto(kitUrl);
    await expect(fresh.getByText(`${IMPROVEMENT} · 0 of 2 weeks done`)).toBeVisible();
    await expect(fresh.getByRole("checkbox", { name: "Two call lights at once" })).toBeChecked();
    await fresh.goto(`/careers/${TRACK}/questions/${FOLLOW_UP_Q}?answer=${rec.ids.follow_up_answer}`);
    await expect(fresh.getByRole("region", { name: /^Feedback on (try 1|your answer) from/ }).getByLabel(`Score ${rec.facts.follow_up_score} out of 100`)).toBeVisible();
    await device.close();
    check("a fresh sign-in on another browser finds the kit, its story and the follow-up's own score");

    // Every id, by the API, with a new token: the same records and the same links between them.
    const auth = await signInApi(request, acct.email);
    const t = await api<{ requirement_list: { id: string; text: string }[]; action_links?: { action_id: string }[]; experience: { id: string; requirement_ids: string[] }[] }>(request, auth, "get", `/api/v1/targets/${targetId}`);
    expect(t.requirement_list.map((r) => r.id)).toEqual(rec.ids.requirements);
    expect((t.action_links ?? []).map((l) => l.action_id)).toContain(actionId);
    const assess = t.requirement_list.find((r) => r.text === REQ_ASSESS)!.id;
    expect(t.experience.map((e) => [e.id, e.requirement_ids])).toEqual([[storyId, [assess]]]);
    const a = await api<Action>(request, auth, "get", `/api/v1/me/actions/${actionId}`);
    expect(a.source.interview_id).toBe(interviewId);
    expect(a.occurrences.map((o) => o.id)).toEqual(rec.ids.occurrences);
    const review = await api<{ improvements: { title: string; action_id: string | null }[] }>(request, auth, "get", `/api/v1/interviews/${interviewId}/review`);
    expect(review.improvements.find((i) => i.title === IMPROVEMENT)?.action_id).toBe(actionId);
    const base = await api<QAnswer[]>(request, auth, "get", `/api/v1/careers/${TRACK}/questions/${BASELINE_Q}/answers`);
    expect(base.map((x) => x.id).sort()).toEqual([rec.ids.baseline_answer, rec.ids.retry_answer].sort());
    const fu = await api<QAnswer[]>(request, auth, "get", `/api/v1/careers/${TRACK}/questions/${FOLLOW_UP_Q}/answers`);
    expect(fu.map((x) => [x.id, x.follows_up_answer_id])).toEqual([[rec.ids.follow_up_answer, rec.ids.retry_answer]]);
    const kit = await api<{ checklist: { action_id?: string | null }[]; stories: { id: string }[] }>(request, auth, "get", `/api/v1/me/applications/${rec.ids.application}/events/${rec.ids.event}/kit`);
    expect(kit.checklist.map((c) => c.action_id).filter(Boolean)).toEqual([actionId]);
    expect(kit.stories.map((x) => x.id)).toEqual([storyId]);
    check("by the API with a new token: the target's requirement ids and its link to the action and to the story (by the patient-assessment requirement), the action (from this interview, its two occurrences), the review's link to it, the three answers and the follow-up's link to the retry, the kit's action and story");
  });

  await rec.step("No secret in the logs", async (check) => {
    const log = readFileSync(ACCESS_LOG, "utf8");
    expect(log.length).toBeGreaterThan(0);
    expect(log).not.toContain(CANARY);
    check("the API's access log for this run doesn't contain the canary typed into the story");
  });
}
