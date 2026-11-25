import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import type { APIRequestContext, Page } from "@playwright/test";

import { JUDGE_NEEDED, SE_TRACK, judgeReady } from "./engineer-journey";
import { devices, expect, setTheme, test } from "./fixtures";
import { ACCESS_LOG } from "./ports";
import { type Account, Recorder, api, answerRound, newAccount, signIn } from "./preparation-journey";

/**
 * Volume 20 across two devices and a backup file (Volume 20, prompt 10; docs/PREPARATION_JOURNEY.md,
 * "Brought back and compared"), against the real API and the real judge in gVisor. On a desktop, one
 * account saves two questions for review from a round's review and downloads its backup; the file,
 * edited as a file could be to claim each ladder well along, is restored on a fresh account through
 * the page, and both start afresh (prompt 1); a phone signed in to that account sees them. On the
 * phone a scenario is finished twice and the second run is compared with the first in the contract's
 * words (prompt 2); on the desktop a sample-answer reading is sent twice and the second says the
 * explanation was seen with the first's result, at its time (prompt 3); on the phone a run of the third
 * test-design exercise is judged for real (prompt 9). Then the phone undoes the restore, which takes
 * the two questions and nothing else. Every page is checked at 412 and 360 px for sideways scrolling,
 * axe finds nothing on the new sections in either theme, and a canary typed into a case is never in
 * the API's log. Synthetic accounts; the judge's result recorded as it gave it.
 */
test.skip(process.env.E2E_JUDGE !== "1", `This journey ${JUDGE_NEEDED}.`);

const QUESTIONS = ["e-good-0", "e-steps-0"];
const ANSWERS = [
  "When a test fails I reproduce it first, then read the failing case and the stack trace, form one hypothesis and check it with a small change.",
  "I narrow the problem down: reproduce, isolate the smallest failing input, add a test for it, fix the cause, and keep the test so it can't come back.",
];
const EXERCISE = "tests-count-pairs";
const LESSON = "cmp-relevance";
const CANARY = "CANARY-brought-back-9c2d4-not-a-real-secret";

/** No sideways scroll at 412 and 360 px, whatever the page's own width, then back to it. */
async function fitsBothWidths(page: Page, where: string, fitted: string[]): Promise<void> {
  const size = page.viewportSize()!;
  for (const width of [412, 360]) {
    await page.setViewportSize({ width, height: size.height });
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    expect(fits, `${where}: the page scrolls sideways at ${width} px`).toBe(true);
  }
  await page.setViewportSize(size);
  fitted.push(where);
}

async function axeBoth(page: Page, selector: string, where: string, scanned: string[]): Promise<void> {
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(selector).analyze();
    expect(scan.violations.map((v) => v.id), `${where} (${theme})`).toEqual([]);
  }
  scanned.push(where);
}

type QueueItem = { id: string; title: string; question_id: string; interval_days: number; reviews: number; last_score: number | null; due: boolean; due_at: string };
type Queue = { due: QueueItem[]; upcoming: QueueItem[]; disputed: QueueItem[] };
const queued = async (request: APIRequestContext, acct: Account) => {
  const q = await api<Queue>(request, acct.auth, "get", "/api/v1/me/reviews");
  return [...q.due, ...q.upcoming, ...q.disputed];
};

const cont = (page: Page) => page.getByRole("button", { name: "Continue" });
async function choose(page: Page, label: RegExp) {
  await page.getByLabel(label).check();
  await page.getByRole("button", { name: "Confirm this decision" }).click();
}
const SBAR =
  "Situation: bed 3 is short of breath and his saturation is dropping. Background: day 1 after hip surgery. " +
  "Assessment: I'm worried he's deteriorating. Recommendation: please come and see him now.";

test("Volume 20 across two devices and a backup file, test design judged for real", async ({ page: desk, browser, request }, info) => {
  test.setTimeout(420_000);
  const rec = new Recorder(info, "brought-back");
  const fitted: string[] = [];
  const scanned: string[] = [];
  const phoneContext = await browser.newContext({ ...devices["Pixel 7"] });
  const phone = await phoneContext.newPage();
  const onPhone = { made: "phone" as const, read: ["phone" as const] };
  const onDesk = { made: "desktop" as const, read: ["desktop" as const] };
  try {
    const source = await newAccount(request, "brought-back-source", SE_TRACK);
    const acct = await newAccount(request, "brought-back", SE_TRACK);
    rec.facts.phone_viewport = `${devices["Pixel 7"].viewport.width}x${devices["Pixel 7"].viewport.height}`;
    rec.facts.exercise = EXERCISE;
    let file = "";
    let titles: string[] = [];

    await rec.step("The judge is ready", async (check) => {
      await judgeReady(request, acct, rec);
      check(`/capabilities: code execution on, the judge "ready", the coach "${rec.facts.ai_provider}"`);
    });

    await rec.step("Two questions saved for review from a round's review, on the desktop", async (check) => {
      await signIn(desk, source.email);
      const iv = await api<{ id: string }>(request, source.auth, "post", "/api/v1/interviews", { kind: "questions", track: SE_TRACK, question_ids: QUESTIONS });
      await desk.goto(`/interviews/${iv.id}`);
      await answerRound(desk, ANSWERS);
      const detail = desk.locator(".review-detail");
      for (let i = 0; i < QUESTIONS.length; i++) {
        await desk.locator(".review__timeline .timeline-item").nth(i).click(); // the review opens on any of them
        await expect(detail.getByRole("heading", { level: 3 })).toHaveText(new RegExp(`^${i + 1}\\. `));
        await detail.getByRole("button", { name: "Save for later review" }).click();
        await expect(detail.getByText("In your review queue")).toBeVisible();
      }
      const saved = await queued(request, source);
      expect(saved.map((s) => s.question_id).sort()).toEqual([...QUESTIONS].sort());
      titles = saved.map((s) => s.title);
      rec.ids.source_interview = iv.id;
      check(`a two-question round answered on the desktop; both saved with "Save for later review" in its review ("In your review queue" each time)`);
      check(`by the API: the source account's queue holds ${QUESTIONS.join(" and ")}`);
    }, ["built-in coach"], onDesk);

    await rec.step("A backup file downloaded, then edited to claim each ladder well along", async (check) => {
      await desk.goto("/settings");
      const [download] = await Promise.all([desk.waitForEvent("download"), desk.getByRole("button", { name: "Download my data" }).click()]);
      file = info.outputPath("brought-back-backup.json");
      await download.saveAs(file);
      const doc = JSON.parse(readFileSync(file, "utf8")) as { export_version: number; review_queue: Record<string, unknown>[] };
      expect(doc.review_queue).toHaveLength(2);
      // As a file could be edited: each ladder well along, a perfect score. The restore must take none of it.
      for (const r of doc.review_queue) Object.assign(r, { step: 4, reviews: 7, last_score: 100, due_at: "2026-01-01T00:00:00+00:00" });
      writeFileSync(file, JSON.stringify(doc));
      rec.ids.file_sha256 = createHash("sha256").update(readFileSync(file)).digest("hex");
      rec.facts.file_version = doc.export_version;
      check(`"Download my data" gave a version ${doc.export_version} file with 2 review_queue records`);
      check(`edited to claim step 4, 7 reviews and a score of 100 for each; the edited file's sha256 is ${rec.ids.file_sha256}`);
      await desk.goto("/settings");
      await desk.getByRole("region", { name: "Sign out" }).getByRole("button", { name: "Sign out", exact: true }).click();
      await expect(desk).not.toHaveURL(/\/settings/);
    }, undefined, onDesk);

    await rec.step("Restored on a fresh account through the page, each starting afresh", async (check) => {
      await signIn(desk, acct.email);
      await desk.goto("/settings/restore");
      await desk.getByLabel("Backup file").setInputFiles(file);
      const pv = desk.getByRole("region", { name: "2. Check what would be added" });
      const box = pv.getByRole("checkbox", { name: "Questions saved for review, each starting afresh: 2 new" });
      await expect(box).toBeChecked();
      await expect(pv).toContainText("Ladders, due dates, scores, review counts and the points each was saved for aren't restored");
      await axeBoth(desk, ".restore-preview", "the restore preview", scanned);
      await fitsBothWidths(desk, "the restore preview", fitted);
      await pv.getByRole("button", { name: /^Restore / }).click();
      await expect(desk.getByText(/^Restored: .*2 questions saved for review/)).toBeVisible();
      const [batch] = await api<{ id: string; status: string; categories: string[] }[]>(request, acct.auth, "get", "/api/v1/me/restore/batches");
      expect(batch!.status).toBe("applied");
      rec.ids.restore_batch = batch!.id;
      const items = await queued(request, acct);
      expect(items.map((i) => i.question_id).sort()).toEqual([...QUESTIONS].sort());
      const tomorrow = Date.now() + 24 * 3600 * 1000;
      for (const i of items) {
        expect({ interval: i.interval_days, reviews: i.reviews, score: i.last_score, due: i.due }).toEqual({ interval: 1, reviews: 0, score: null, due: false });
        expect(Math.abs(Date.parse(i.due_at) - tomorrow)).toBeLessThan(10 * 60 * 1000);
      }
      rec.ids.restored_review_items = items.map((i) => i.id);
      check(`the preview offered "Questions saved for review, each starting afresh: 2 new" and said ladders, due dates, scores, review counts and points aren't restored`);
      check(`restore batch ${batch!.id}: applied (${batch!.categories.join(", ")})`);
      check("by the API: both on the ladder's first rung (1 day, 0 reviews, no score, first due a day from now), none of what the edited file claimed");
    }, undefined, onDesk);

    await rec.step("The phone sees the two questions", async (check) => {
      await signIn(phone, acct.email);
      await phone.goto("/reviews");
      for (const t of titles) await expect(phone.getByRole("listitem", { name: t })).toBeVisible();
      await fitsBothWidths(phone, "the review queue", fitted);
      check(`the phone's review queue lists "${titles.join("\" and \"")}"`);
    }, undefined, { made: "desktop", read: ["phone"] });

    let firstRun = "";
    let secondRun = "";
    await rec.step("A scenario finished twice on the phone, the second compared with the first", async (check) => {
      const begin = async () => {
        await phone.goto("/scenarios/rn-two-patients");
        await phone.getByRole("button", { name: "Start the scenario" }).click();
        await expect(phone).toHaveURL(/\/scenarios\/attempts\//);
      };
      await begin();
      await cont(phone).click();
      await cont(phone).click();
      await choose(phone, /Bed 7, because their medicine is due/);
      await cont(phone).click();
      await cont(phone).click();
      await choose(phone, /Recheck him in 30 minutes/);
      await cont(phone).click();
      await phone.getByLabel("Your response").fill("I would escalate earlier using SBAR because his breathing and saturation were getting worse.");
      await phone.getByRole("button", { name: "Send response" }).click();
      const first = phone.getByRole("region", { name: "Debrief" });
      await expect(first).toContainText("Not compared: the first finished run of this scenario");
      firstRun = new URL(phone.url()).pathname.split("/").pop()!;
      await begin();
      await cont(phone).click();
      await cont(phone).click();
      await choose(phone, /Bed 3, and ask a colleague/);
      await cont(phone).click();
      await choose(phone, /Follow the unit protocol/);
      await phone.getByLabel("Your response").fill(SBAR);
      await phone.getByRole("button", { name: "Send response" }).click();
      const compared = phone.getByRole("region", { name: "Debrief" }).getByRole("region", { name: "Compared with your previous attempt" });
      await expect(compared).toContainText("Partly comparable: the runs took different paths");
      await expect(compared).toContainText("0 strong, 0 acceptable, 2 risky · ended: Escalation delayed (simulated)");
      await expect(compared).toContainText("This one: 2 strong, 0 acceptable, 0 risky · ended: Escalated promptly (simulated)");
      secondRun = new URL(phone.url()).pathname.split("/").pop()!;
      rec.ids.scenario_runs = [firstRun, secondRun];
      rec.facts.scenario_compared = (await compared.innerText()).split(/\s*\n+\s*/).filter(Boolean).join(" / ");
      await axeBoth(phone, ".submission-compared", "the second scenario run's comparison", scanned);
      await fitsBothWidths(phone, "the second scenario run's debrief", fitted);
      check(`the first run's debrief: "Not compared: the first finished run of this scenario"`);
      check(`the second's, beside the first: "${rec.facts.scenario_compared}"`);
    }, undefined, onPhone);

    await rec.step("A sample-answer reading sent twice on the desktop, the second saying the explanation was seen", async (check) => {
      const reading = async () => {
        await desk.goto(`/compare/${LESSON}`);
        await desk.getByRole("list", { name: "Answer A, sentence by sentence" }).getByRole("listitem").nth(1).getByRole("button", { name: "Strength" }).click();
        await desk.getByLabel("Why is it a strength?").fill("Gives a rule and the reason for it.");
        const sending = desk.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith(`/me/comparisons/${LESSON}/attempts`));
        await desk.getByRole("button", { name: "Compare with the explanation" }).click();
        return (await (await sending).json()) as { id: string; created_at: string };
      };
      const result = desk.locator("section", { has: desk.locator("#cmp-result") });
      const first = await reading();
      await expect(result.locator(".attempt-conditions")).toContainText("No in-app help recorded");
      const second = await reading();
      const help = result.locator(".attempt-conditions li").filter({ hasText: "Solution revealed: The explanation was shown with an earlier reading's result before this was sent" });
      await expect(help).toHaveCount(1);
      expect(Date.parse((await help.locator("time").getAttribute("datetime"))!)).toBe(Date.parse(first.created_at));
      rec.ids.readings = [first.id, second.id];
      await axeBoth(desk, ".attempt-conditions", "the second reading's conditions", scanned);
      await fitsBothWidths(desk, "the second reading's result", fitted);
      check(`the first reading: "No in-app help recorded"; its result showed the explanation`);
      check(`the second: "Solution revealed: The explanation was shown with an earlier reading's result before this was sent", at the first's time (${first.created_at})`);
    }, undefined, onDesk);

    await rec.step("A run of the third test-design exercise judged for real, on the phone", async (check) => {
      await phone.goto(`/test-design/${EXERCISE}`);
      await expect(phone.locator("#main")).toContainText("Its review is owed: not yet reviewed by the project author.");
      const cases: [string, string, string, string][] = [
        ["3, 1", "6", "0", `half the target (${CANARY})`], ["1, 5, 2, 4", "6", "2", "two pairs"], ["2, 2, 2", "4", "3", "repeated values"], ["4, 7, 2", "6", "1", "a pair at the end"],
      ];
      for (const [i, [nums, target, expected, note]] of cases.entries()) {
        if (i > 0) await phone.getByRole("button", { name: "Add a case" }).click();
        await phone.getByLabel(/^nums/).nth(i).fill(nums);
        await phone.getByLabel(/^target/).nth(i).fill(target);
        await phone.getByLabel("Expected output").nth(i).fill(expected);
        await phone.getByLabel("What it covers (optional)").nth(i).fill(note);
      }
      const posted = phone.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith(`/me/test-design/${EXERCISE}/runs`));
      await phone.getByRole("button", { name: "Run my cases" }).click();
      const id = ((await (await posted).json()) as { id: string }).id;
      const shows = phone.getByRole("region", { name: "What your cases show" });
      await expect(shows).toContainText("Your cases tell 4 of the 4 authored faulty versions apart", { timeout: 90_000 });
      const run = await api<{ id: string; status: string; status_detail: string; created_at: string; judged_at: string | null; report: { report_version: number; caught: number; total: number } }>(
        request, acct.auth, "get", `/api/v1/me/test-design/runs/${id}`);
      expect([run.status, run.report.caught, run.report.total]).toEqual(["done", 4, 4]);
      rec.ids.test_design_run = id;
      rec.facts.test_design_run = `${run.status}: told apart ${run.report.caught} of ${run.report.total} faulty versions (report v${run.report.report_version}); "${run.status_detail}"; ` +
        `${run.judged_at ? Date.parse(run.judged_at) - Date.parse(run.created_at) : "?"} ms from the request to the result`;
      await fitsBothWidths(phone, "the test-design run's report", fitted);
      check(`the page says the exercise's review is owed; four cases judged in the sandbox: ${rec.facts.test_design_run}`);
      check(`the report says "${(await shows.locator("p").first().innerText()).trim()}"`);
    }, ["real judge"], onPhone);

    await rec.step("The restore undone on the phone: the two questions go, nothing else", async (check) => {
      await phone.goto("/settings/restore");
      phone.once("dialog", (d) => void d.accept());
      await phone.getByRole("button", { name: "Remove what this added" }).click();
      await expect(phone.getByText(/Removed 2; kept 0 you'd changed since; 0 were already gone\./)).toBeVisible();
      await fitsBothWidths(phone, "the restore page after the undo", fitted);
      const [batch] = await api<{ id: string; status: string }[]>(request, acct.auth, "get", "/api/v1/me/restore/batches");
      expect([batch!.id, batch!.status]).toEqual([rec.ids.restore_batch, "removed"]);
      expect(await queued(request, acct)).toEqual([]);
      // Nothing else: the scenario runs, the readings and the test-design run are all still there.
      const runs = await api<{ id: string }[]>(request, acct.auth, "get", "/api/v1/me/scenario-attempts");
      expect(runs.map((r) => r.id).sort()).toEqual([firstRun, secondRun].sort());
      const readings = await api<{ id: string }[]>(request, acct.auth, "get", `/api/v1/me/comparisons/${LESSON}/attempts`);
      expect(readings.map((r) => r.id).sort()).toEqual([...(rec.ids.readings as string[])].sort());
      expect((await api<{ id: string }>(request, acct.auth, "get", `/api/v1/me/test-design/runs/${rec.ids.test_design_run}`)).id).toBe(rec.ids.test_design_run);
      check(`"Remove what this added" said "Removed 2; kept 0 you'd changed since; 0 were already gone."; batch ${batch!.id} is removed`);
      check("checked through the API, since the page shows only the batch: the review queue is empty, and the two scenario runs, the two readings and the test-design run are all still there");
    }, undefined, onPhone);

    await rec.step("Nothing typed reached the API's log", async (check) => {
      expect(readFileSync(ACCESS_LOG, "utf8")).not.toContain(CANARY);
      check("the canary typed into the first case's note isn't in the API's log");
      rec.facts.fitted = fitted.join(", ");
      rec.facts.axe = scanned.join(", ");
      check(`no sideways scroll at 412 or 360 px on: ${fitted.join("; ")}`);
      check(`axe found nothing, in dark and light, on: ${scanned.join("; ")}`);
    });
  } finally {
    rec.write(true);
    await phoneContext.close();
  }
});
