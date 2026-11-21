import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { devices, type APIRequestContext, type Browser, type BrowserContext, type Page, type TestInfo } from "@playwright/test";

import { BASELINE, PROBLEM, PROBLEM_TITLE, RESUBMISSION, SE_CANARY, SE_TRACK, judgeReady, paste, submitAndJudge, verdict, type Sub } from "./engineer-journey";
import { expect } from "./fixtures";
import { ACCESS_LOG, E2E_DATABASE_URL } from "./ports";
import { Recorder, api, newAccount, signIn, signInApi } from "./preparation-journey";

/**
 * One engineer on two devices, judged for real (Volume 16, prompt 10; docs/PREPARATION_JOURNEY.md,
 * "An engineer on two devices"): on a desktop, a hint, then a baseline and a resubmission judged in
 * the gVisor sandbox and compared by the one contract; on a phone signed in to the same account,
 * both read the same by id, the comparison word for word; the plan's update offers the judged code
 * as new evidence, accepted on the phone and seen on the desktop after a reload; a coding interview
 * checked on the phone ("I've checked this") and left to time out is recorded as checked, with the
 * time, on both. Each step records its ids and which device made the change and which read it. A
 * canary typed into the code on each device is never in the API's log. The judge's verdicts are
 * recorded as it gave them; without a ready judge the journey stops at its first step, saying why.
 *
 * The one thing it doesn't wait for is a 10-minute interview's clock (the shortest there is): the
 * interview's deadline is moved to 75 seconds away in the test database, then the clock runs out
 * for real, on the server, while the phone has the page open. Synthetic accounts and code only.
 */

export const PHONE_CANARY = "CANARY-engineer-phone-7e2b1-not-a-real-secret";
const PHONE_CODE = `class Solution {
    // Checked on a phone before time ran out. (${PHONE_CANARY})
    public int[] twoSum(int[] nums, int target) {
        return new int[] {0, 1};
    }
}`;
const CHECK_KEPT = "Checked. If time runs out before you finish, the review will say you checked this, or name what changed after.";
const CHECKED_TIMED_OUT = "You checked this before time ran out.";
const PYTHON = process.env.PYTHON ?? "python";

async function noSidewaysScroll(page: Page, where: string): Promise<void> {
  const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
  expect(fits, `${where}: the page scrolls sideways at phone width`).toBe(true);
}

/** The text on screen, with its spacing as a reader sees it. */
const words = async (page: Page, region: string) =>
  ((await page.getByRole("region", { name: region }).textContent()) ?? "").replace(/\s+/g, " ").trim();

/** Brings a running interview's deadline to `seconds` from now in the browser suite's own database
 * (the shortest interview is 10 minutes): the clock then runs out for real, on the server. */
function bringDeadlineNear(interviewId: string, seconds: number): void {
  const db = resolve(process.cwd(), "../backend", E2E_DATABASE_URL.replace("sqlite:///./", ""));
  execFileSync(PYTHON, ["-c", `
import sqlite3, sys
from datetime import datetime, timedelta, timezone
db, sid, secs = sys.argv[1], sys.argv[2], int(sys.argv[3])
when = (datetime.now(timezone.utc) + timedelta(seconds=secs)).replace(tzinfo=None).isoformat(sep=" ")
c = sqlite3.connect(db)
n = c.execute("update practice_sessions set deadline_at = ? where id = ? and status = 'in_progress'", (when, sid)).rowcount
c.commit()
assert n == 1, f"{n} interviews moved"
`, db, interviewId, String(seconds)]);
}

interface Interview { id: string; status: string; ending?: string | null }
interface FeedbackRead { text: string; checked: boolean | null; confirmed: { at: string; matched: boolean } | null }
interface Plan {
  version: number;
  news: { text: string; submissions: number; by_skill: { skill: string | null; text: string }[]; rule: string | null } | null;
  read_submissions: { id: string; title: string | null; verdict: string | null }[] | null;
}

export async function engineerDevices(page: Page, context: BrowserContext, browser: Browser, request: APIRequestContext, info: TestInfo): Promise<Recorder> {
  const rec = new Recorder(info, "engineer-devices");
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const phoneContext = await browser.newContext({ ...devices["Pixel 7"], permissions: ["clipboard-read", "clipboard-write"] });
  try {
    await run(rec, page, await phoneContext.newPage(), request);
  } finally {
    rec.write(true);
    await phoneContext.close();
  }
  return rec;
}

async function run(rec: Recorder, desk: Page, phone: Page, request: APIRequestContext) {
  const acct = await newAccount(request, "engineer-devices", SE_TRACK);
  rec.facts.phone_viewport = `${devices["Pixel 7"].viewport.width}x${devices["Pixel 7"].viewport.height}`;
  let baseline: Sub | null = null;
  let resubmission: Sub | null = null;
  let deskComparison = "";
  let interviewId = "";
  let confirmedAt = "";

  await rec.step("The judge is ready", async (check) => {
    await judgeReady(request, acct, rec);
    check(`/capabilities: code execution on, the judge "ready" (submissions are judged in the sandbox), the coach "${rec.facts.ai_provider}"`);
  });

  await signIn(desk, acct.email);

  await rec.step("The plan to start from", async (check) => {
    await desk.goto("/plan");
    await expect(desk.getByText(/^Version 1\./)).toBeVisible();
    await expect(desk.getByText(/the judge's verdicts on code you submit: to problems, and to debugging exercises/)).toBeVisible();
    const p = await api<Plan>(request, acct.auth, "get", "/api/v1/me/plan");
    expect(p.version).toBe(1);
    expect(p.news).toBeNull();
    rec.ids.plan_version_1 = p.version;
    check("version 1 of the plan, nothing new yet; the page says the plan reads the judge's verdicts on submitted code (not runs)");
  }, undefined, { made: "desktop", read: ["desktop"] });

  await rec.step("A hint, then a baseline judged for real", async (check) => {
    await desk.goto(`/problems/${PROBLEM}`);
    await expect(desk.locator(".monaco-editor")).toBeVisible();
    await paste(desk, BASELINE);
    const coach = desk.getByRole("region", { name: "AI coach" });
    await coach.getByRole("button", { name: "Get a hint" }).click();
    const panel = coach.locator("section").filter({ has: desk.getByRole("heading", { name: "What the coach will read" }) });
    await panel.getByRole("button", { name: "Ask for the level 1 hint" }).click();
    await expect(coach.getByText("Level 1 · Nudge")).toBeVisible();
    check("a level 1 hint, from the preview of what the coach reads");
    const { sub, seenMs } = await submitAndJudge(desk, request, acct, "Some tests failed. Check the cases below.");
    expect(sub.status).toBe("FAILED");
    baseline = sub;
    rec.ids.baseline_submission = sub.id;
    rec.judged.push(verdict("A hint, then a baseline judged for real", sub, seenMs));
    check(`judged in the sandbox: ${sub.status}, ${sub.result!.passed_count}/${sub.result!.total_count} tests passed`);
  }, ["real judge", "built-in coach"], { made: "desktop", read: ["desktop"] });

  await rec.step("A resubmission judged for real, compared by the contract", async (check) => {
    await paste(desk, RESUBMISSION);
    const { sub, seenMs } = await submitAndJudge(desk, request, acct, "All tests passed. Nice work.");
    expect(sub.status).toBe("PASSED");
    resubmission = sub;
    rec.ids.resubmission = sub.id;
    rec.judged.push(verdict("A resubmission judged for real, compared by the contract", sub, seenMs));
    expect(sub.compared?.previous.id).toBe(baseline!.id);
    await desk.goto(`/history/submissions/${sub.id}`);
    deskComparison = await words(desk, "Compared with your previous submission");
    expect(deskComparison).toContain(sub.compared!.comparison.explanation);
    expect(deskComparison).not.toMatch(/improv|better/i);
    rec.facts.comparison_outcome = sub.compared!.comparison.outcome;
    rec.facts.comparison = deskComparison;
    check(`judged in the sandbox: ${sub.status}, ${sub.result!.passed_count}/${sub.result!.total_count}; compared with the baseline: "${sub.compared!.comparison.explanation}"`);
  }, ["real judge"], { made: "desktop", read: ["desktop"] });

  await signIn(phone, acct.email);
  const phoneAuth = await signInApi(request, acct.email);

  await rec.step("Both submissions read on the phone, the comparison word for word", async (check) => {
    for (const sub of [baseline!, resubmission!]) {
      await phone.goto(`/history/submissions/${sub.id}`);
      await expect(phone.locator(".attempt-conditions")).toBeVisible();
      const same = await api<Sub>(request, phoneAuth, "get", `/api/v1/submissions/${sub.id}`);
      expect({ id: same.id, status: same.status, result: same.result?.passed_count }).toEqual({ id: sub.id, status: sub.status, result: sub.result?.passed_count });
      await noSidewaysScroll(phone, `submission ${sub.id}`);
    }
    const phoneComparison = await words(phone, "Compared with your previous submission");
    expect(phoneComparison).toBe(deskComparison);
    check(`by id, the phone's API reads both verdicts as judged (${baseline!.status}, ${resubmission!.status}); its page's comparison is the desktop's, word for word; no sideways scroll`);
  }, undefined, { made: "desktop", read: ["phone"] });

  await rec.step("The plan offers the judged code, accepted on the phone", async (check) => {
    await phone.goto("/plan");
    const news = phone.getByRole("region", { name: /2 submissions \(1 not passed\) since this plan\./ });
    await expect(news).toBeVisible();
    const skills = news.getByRole("list", { name: "What it would change, by skill" });
    await expect(skills).toContainText(`“${PROBLEM_TITLE}” didn't pass (tests failed), then passed`);
    await expect(news).toContainText("A verdict is never turned into a score.");
    const before = await api<Plan>(request, phoneAuth, "get", "/api/v1/me/plan");
    rec.facts.plan_news = before.news!.text;
    rec.facts.plan_news_by_skill = before.news!.by_skill.map((g) => g.text).join(" | ");
    await noSidewaysScroll(phone, "the plan");
    await news.getByRole("button", { name: "Update my plan" }).click();
    await expect(phone.getByText("Your plan is now version 2. What changed is listed with it.")).toBeVisible();
    const read = phone.getByRole("list", { name: "Code this update read" });
    await expect(read.getByRole("listitem")).toHaveCount(2);
    const after = await api<Plan>(request, phoneAuth, "get", "/api/v1/me/plan");
    expect(after.version).toBe(2);
    expect(after.read_submissions?.map((r) => r.id)).toEqual([baseline!.id, resubmission!.id]);
    rec.ids.plan_version_2_read = after.read_submissions!.map((r) => r.id);
    check(`offered on the phone: "${before.news!.text}", by skill: "${rec.facts.plan_news_by_skill}"; accepted there: version 2 records the two submissions it read, by id`);
  }, undefined, { made: "phone", read: ["phone"] });

  await rec.step("The update seen on the desktop after a reload", async (check) => {
    await desk.goto("/plan");
    await desk.reload();
    await expect(desk.getByText(/^Version 2\./)).toBeVisible();
    const read = desk.getByRole("list", { name: "Code this update read" });
    await expect(read.getByRole("link")).toHaveCount(2);
    await expect(read.getByRole("link").first()).toHaveAttribute("href", `/history/submissions/${baseline!.id}`);
    await expect(desk.getByRole("region", { name: /since this plan/ })).toHaveCount(0);
    check("the desktop shows version 2, the code it read (both submissions, linked by id) and nothing left to update");
  }, undefined, { made: "phone", read: ["desktop"] });

  await rec.step("A coding interview checked on the phone, left to time out", async (check) => {
    await phone.goto("/interviews");
    await phone.getByLabel("Problem", { exact: true }).selectOption(PROBLEM);
    await phone.getByText("15 min").click();
    await phone.getByRole("button", { name: "Start interview" }).click();
    await expect(phone).toHaveURL(/\/interviews\/[0-9a-f-]+$/);
    interviewId = phone.url().split("/").pop()!;
    rec.ids.interview = interviewId;
    await expect(phone.locator(".monaco-editor")).toBeVisible();
    await paste(phone, PHONE_CODE);
    await phone.getByLabel("Your answer").fill("I'd keep a hash map of each value's index and look up the complement.");
    await phone.getByRole("button", { name: "Send" }).click();
    await expect(phone.getByLabel("Interviewer is typing")).toHaveCount(0);
    check("started on the phone (15 minutes), the code (with the phone's canary) sent with a message");
    bringDeadlineNear(interviewId, 75);
    await phone.reload();
    const nearly = phone.locator(".interview__nearly-up");
    await expect(nearly).toContainText("Time is nearly up.");
    await nearly.getByRole("button", { name: "Check what the feedback will read" }).click();
    const confirming = phone.waitForResponse((r) => new URL(r.url()).pathname === `/api/v1/interviews/${interviewId}/feedback/confirm`);
    await phone.getByRole("button", { name: "I've checked this" }).click();
    const confirmed = (await (await confirming).json()) as { at: string };
    confirmedAt = confirmed.at;
    await expect(phone.getByText(CHECK_KEPT)).toBeVisible();
    rec.facts.checked_at = confirmedAt;
    check(`with 75 seconds left (moved in the test database; the clock then ran for real): "Check what the feedback will read", then "I've checked this", kept at ${confirmedAt}`);
    await noSidewaysScroll(phone, "the interview");
    await expect.poll(async () => (await api<Interview>(request, phoneAuth, "get", `/api/v1/interviews/${interviewId}`)).status, { timeout: 150_000, intervals: [5_000] }).toBe("expired");
    check("time ran out on the server, the phone's page open: the interview is \"expired\"");
  }, ["built-in coach"], { made: "phone", read: ["phone"] });

  await rec.step("Recorded as checked, with the time, on both devices", async (check) => {
    const review = await api<{ feedback_read: FeedbackRead }>(request, acct.auth, "get", `/api/v1/interviews/${interviewId}`);
    expect(review.feedback_read.text).toBe(CHECKED_TIMED_OUT);
    expect(review.feedback_read.confirmed?.at).toBe(confirmedAt);
    for (const [page, device] of [[phone, "phone"], [desk, "desktop"]] as const) {
      await page.goto(`/interviews/${interviewId}`);
      const section = page.locator(".feedback-read");
      await expect(section).toContainText(CHECKED_TIMED_OUT);
      await expect(section.locator("time")).toHaveAttribute("dateTime", confirmedAt);
      if (device === "phone") await noSidewaysScroll(page, "the interview's review");
    }
    check(`"${CHECKED_TIMED_OUT}" with the time of the check (${confirmedAt}), on the phone and on the desktop`);
  }, undefined, { made: "phone", read: ["phone", "desktop"] });

  await rec.step("Nothing typed reached the API's log", async (check) => {
    const log = readFileSync(ACCESS_LOG, "utf8");
    expect(log).not.toContain(SE_CANARY);
    expect(log).not.toContain(PHONE_CANARY);
    check(`neither canary (the desktop's code, the phone's code) is in the API's log`);
  });
}
