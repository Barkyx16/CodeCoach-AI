import { readFileSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import type { APIRequestContext, Page } from "@playwright/test";

import { JUDGE_NEEDED, SE_TRACK, judgeReady } from "./engineer-journey";
import { expect, setTheme, test } from "./fixtures";
import { ACCESS_LOG } from "./ports";
import { type Account, Recorder, api, newAccount, signIn } from "./preparation-journey";

/**
 * Volume 19 on a phone, with test design judged for real (Volume 19, prompt 10;
 * docs/PREPARATION_JOURNEY.md, "Kept and accounted for, on a phone"). In the mobile project (a Pixel 7,
 * 412 px wide), against the real API and the real judge in gVisor: a move between collections whose
 * reply is lost, then a reload, reads as the first reply did, each item there once (prompt 1); a
 * question removed from the review queue, the page reloaded, comes back from "Removed recently" as it
 * was (prompt 2); two test-design runs judged in the sandbox with the faulty versions shown between
 * them: the second says when they were shown (prompt 3) and is partly comparable with the first
 * (prompt 4); History lists both runs, each opening its report. Every page is checked at 412 and 360
 * px for sideways scrolling, axe finds nothing on the new sections in either theme, and a canary typed
 * into a case is never in the API's log. Synthetic account; each run's result recorded as the judge
 * gave it.
 */
test.skip(process.env.E2E_JUDGE !== "1", `This journey ${JUDGE_NEEDED}.`);

const EXERCISE = "tests-count-in-range";
const CANARY = "CANARY-kept-journey-4b7e1-not-a-real-secret";

/** No sideways scroll at the phone's own width (412 px) and at 360 px. */
async function fitsBothWidths(page: Page, where: string, fitted: string[]): Promise<void> {
  const size = page.viewportSize()!;
  for (const width of [size.width, 360]) {
    await page.setViewportSize({ width, height: size.height });
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    expect(fits, `${where}: the page scrolls sideways at ${width} px`).toBe(true);
  }
  await page.setViewportSize(size);
  fitted.push(where);
}

/** axe on a section in both themes: no violations. */
async function axeBoth(page: Page, selector: string, where: string, scanned: string[]): Promise<void> {
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(selector).analyze();
    expect(scan.violations.map((v) => v.id), `${where} (${theme})`).toEqual([]);
  }
  scanned.push(where);
}

interface Run { id: string; status: string; status_detail: string; created_at: string; judged_at: string | null; report: { report_version: number; caught: number; total: number } | null }

/** A run's result as the API keeps the judge's (what the page shows), for the record. */
async function judgedRun(request: APIRequestContext, acct: Account, id: string): Promise<Run> {
  return api<Run>(request, acct.auth, "get", `/api/v1/me/test-design/runs/${id}`);
}
const runRecord = (r: Run) =>
  `${r.status}: told apart ${r.report?.caught} of ${r.report?.total} faulty versions (report v${r.report?.report_version}); ` +
  `"${r.status_detail}"; ${r.judged_at ? Date.parse(r.judged_at) - Date.parse(r.created_at) : "?"} ms from the request to the result`;

async function fill(page: Page, nums: string, lo: string, hi: string, expected: string, note = "") {
  await page.getByLabel(/^nums/).nth(0).fill(nums);
  await page.getByLabel(/^lo/).nth(0).fill(lo);
  await page.getByLabel(/^hi/).nth(0).fill(hi);
  await page.getByLabel("Expected output").nth(0).fill(expected);
  await page.getByLabel("What it covers (optional)").nth(0).fill(note);
}

test("Volume 19 on a phone: a lost move and a removal through reloads, and test design judged for real", async ({ page, request }, info) => {
  test.setTimeout(300_000);
  const rec = new Recorder(info, "kept-and-accounted-for");
  const fitted: string[] = [];
  const scanned: string[] = [];
  const phone = { made: "phone" as const, read: ["phone" as const] };
  try {
    const acct = await newAccount(request, "kept-journey", SE_TRACK);
    rec.facts.viewport = `${page.viewportSize()!.width}x${page.viewportSize()!.height}`;
    rec.facts.exercise = EXERCISE;
    let week1 = "";
    let week2 = "";
    let qs: { id: string; title: string }[] = [];

    await rec.step("The judge is ready", async (check) => {
      await judgeReady(request, acct, rec);
      check(`/capabilities: code execution on, the judge "ready", the coach "${rec.facts.ai_provider}"`);
    });

    await rec.step("Two collections and two saved questions, set up through the API", async (check) => {
      qs = (await api<{ items: { id: string; title: string }[] }>(request, acct.auth, "get", `/api/v1/careers/${SE_TRACK}/questions?page_size=5`)).items;
      const make = async (name: string, ids: string[]) => {
        const c = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/me/collections", { name });
        for (const id of ids) await api(request, acct.auth, "post", `/api/v1/me/collections/${c.id}/items`, { item_type: "question", track: SE_TRACK, ref_id: id });
        return c.id;
      };
      week1 = await make("Week 1", [qs[0]!.id, qs[1]!.id, qs[2]!.id]);
      week2 = await make("Week 2", [qs[3]!.id]);
      for (const q of [qs[0]!, qs[4]!]) await api(request, acct.auth, "post", "/api/v1/me/reviews", { track: SE_TRACK, question_id: q.id });
      rec.ids.collections = [week1, week2];
      check("not a step a learner takes here: the API made \"Week 1\" (three questions) and \"Week 2\" (one), and saved two questions for review");
    });
    await signIn(page, acct.email);

    await rec.step("A move between collections through a lost reply and a reload", async (check) => {
      await page.goto(`/saved/collections/${week1}`);
      for (const q of [qs[0]!, qs[2]!]) await page.getByRole("checkbox", { name: `Select: ${q.title}` }).check();
      await page.getByRole("button", { name: "Move 2 to…" }).click();
      const form = page.getByRole("form", { name: "Move 2 items to another collection" });
      await form.getByLabel("To collection").selectOption({ label: "Week 2 (1 item)" });
      let sent = 0;
      page.on("request", (r) => { if (r.method() === "POST" && r.url().endsWith("/items/transfer")) sent += 1; });
      await page.route("**/items/transfer", async (route) => { await route.fetch(); await route.abort("connectionreset"); });
      await form.getByRole("button", { name: "Move 2 to “Week 2”" }).click();
      const lost = page.getByRole("alert").filter({ hasText: "No reply came" });
      await expect(lost).toBeVisible();
      check(`the server moved them, then the reply was cut off: the page said "${(await lost.innerText()).split("\n")[0]}"`);
      await page.unroute("**/items/transfer");
      await page.reload();
      const notice = page.locator(".earlier-action");
      await expect(notice).toContainText(/Your copy or move from .* arrived\./);
      await expect(notice).toContainText("These are what it did, and nothing was done twice.");
      const outcomes = page.getByRole("region", { name: "What happened: moving to “Week 2”" });
      await expect(outcomes.getByRole("status")).toHaveText("2 moved. Nothing needs attention.");
      rec.facts.move_after_reload = (await outcomes.getByRole("status").innerText()).trim();
      expect(sent, "nothing was sent again after the reload").toBe(1);
      const ids = async (id: string) => (await api<{ item_list: { ref_id: string }[] }>(request, acct.auth, "get", `/api/v1/me/collections/${id}`)).item_list.map((i) => i.ref_id);
      expect(await ids(week2)).toEqual([qs[3]!.id, qs[0]!.id, qs[2]!.id]);
      expect(await ids(week1)).toEqual([qs[1]!.id]);
      await axeBoth(page, ".earlier-action", "the move's notice after the reload", scanned);
      await fitsBothWidths(page, "the collection after the reload", fitted);
      check(`after the reload the page read the first reply: "${rec.facts.move_after_reload}" ("These are what it did, and nothing was done twice."), one POST in all`);
      check("checked through the API, since the page shows only this collection: \"Week 2\" holds each moved question once, \"Week 1\" the one left");
    }, undefined, phone);

    await rec.step("A question removed from the review queue, the page reloaded, put back", async (check) => {
      const reviews = async () => {
        const r = await api<{ due: { title: string; due_at: string }[]; upcoming: { title: string; due_at: string }[] }>(request, acct.auth, "get", "/api/v1/me/reviews");
        return [...r.due, ...r.upcoming];
      };
      const was = (await reviews()).find((i) => i.title === qs[0]!.title)!;
      await page.goto("/reviews");
      await page.getByRole("listitem", { name: qs[0]!.title }).getByRole("button", { name: "Remove" }).click();
      await expect(page.getByRole("button", { name: "Undo" })).toBeVisible();
      await page.reload();
      await expect(page.getByRole("button", { name: "Undo" })).toHaveCount(0);
      await page.getByRole("button", { name: "Removed recently (1)" }).click();
      const row = page.getByRole("list", { name: "Removed recently" }).getByRole("listitem", { name: qs[0]!.title });
      await expect(row).toContainText(/Removed (just now|.* ago)/);
      rec.facts.removed_row = (await row.innerText()).split(/\s*\n+\s*/).filter(Boolean).join(" / ");
      await axeBoth(page, ".removed-recently", "Removed recently", scanned);
      await fitsBothWidths(page, "the review queue with Removed recently open", fitted);
      await row.getByRole("button", { name: `Put back: ${qs[0]!.title}` }).click();
      const said = page.getByText(`“${qs[0]!.title}” is back in your review queue, as it was.`);
      await expect(said).toBeVisible();
      const now = (await reviews()).find((i) => i.title === qs[0]!.title)!;
      expect(now.due_at).toBe(was.due_at);
      check(`removed, then reloaded (the page's Undo gone): "Removed recently (1)" listed "${rec.facts.removed_row}"`);
      check(`Put back said "“${qs[0]!.title}” is back in your review queue, as it was."; through the API, its due date is the one it had (${was.due_at})`);
    }, undefined, phone);

    let first: Run | null = null;
    let second: Run | null = null;
    let shownAt = "";
    const runPosted = () => page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith(`/me/test-design/${EXERCISE}/runs`));
    const shows = page.getByRole("region", { name: "What your cases show" });
    const report = page.locator("section", { has: page.locator("#td-result") });

    await rec.step("A first test-design run, judged for real", async (check) => {
      await page.goto(`/test-design/${EXERCISE}`);
      await fill(page, "1, 5, 9", "2", "8", "1", `ordinary values (${CANARY})`);
      const posted = runPosted();
      await page.getByRole("button", { name: "Run my cases" }).click();
      const id = ((await (await posted).json()) as { id: string }).id;
      await expect(shows).toContainText(/Your cases tell \d of the 4 authored faulty versions apart/, { timeout: 90_000 });
      first = await judgedRun(request, acct, id);
      expect(first.status).toBe("done");
      rec.ids.first_run = id;
      rec.facts.first_run = runRecord(first);
      await expect(report).toContainText("Not compared: the first judged run of this exercise.");
      await expect(report.locator(".attempt-conditions")).toContainText("No in-app help recorded");
      await fitsBothWidths(page, "the first run's report", fitted);
      check(`judged in the sandbox: ${rec.facts.first_run}`);
      check(`the report says "${(await shows.locator("p").first().innerText()).trim()}", "Not compared: the first judged run of this exercise.", and no in-app help before it`);
    }, ["real judge"], phone);

    await rec.step("The faulty versions shown", async (check) => {
      await page.getByRole("button", { name: "Stuck? Show what the faulty versions get wrong" }).click();
      const recorded = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith(`/me/test-design/${EXERCISE}/variants`));
      await page.getByRole("button", { name: "Show the faulty versions" }).click();
      shownAt = ((await (await recorded).json()) as { recorded_at: string }).recorded_at;
      await expect(page.locator("#td-variants")).toBeVisible(); // the shown list (the report has its own)
      rec.facts.variants_shown_at = shownAt;
      check(`"Show the faulty versions" recorded the showing on the account at ${shownAt}, then listed them`);
    }, undefined, phone);

    await rec.step("A second run, judged for real, after the faulty versions were shown", async (check) => {
      await fill(page, "3, 7", "1", "7", "2", "hi itself");
      const posted = runPosted();
      await page.getByRole("button", { name: "Run my cases" }).click();
      const id = ((await (await posted).json()) as { id: string }).id;
      const beside = page.getByRole("region", { name: "Compared with your previous attempt" });
      await expect(beside).toBeVisible({ timeout: 90_000 });
      second = await judgedRun(request, acct, id);
      expect(second.status).toBe("done");
      rec.ids.second_run = id;
      rec.facts.second_run = runRecord(second);
      const help = report.locator(".attempt-conditions li").filter({ hasText: "Solution revealed: The faulty versions were shown before these cases were written" });
      await expect(help).toHaveCount(1);
      expect(Date.parse((await help.locator("time").getAttribute("datetime"))!)).toBe(Date.parse(shownAt));
      await expect(beside).toContainText("Partly comparable: the in-app help differed: before the earlier one, none recorded; before the later one, solution revealed");
      await expect(beside).toContainText(`told apart ${first!.report!.caught} of 4 faulty versions`);
      await expect(beside).toContainText(`This one: told apart ${second.report!.caught} of 4 faulty versions`);
      rec.facts.second_compared = (await beside.locator("p.subtle").innerText()).trim();
      await axeBoth(page, ".submission-compared", "the second run's comparison", scanned);
      await axeBoth(page, ".attempt-conditions", "the second run's conditions", scanned);
      await fitsBothWidths(page, "the second run's report", fitted);
      check(`judged in the sandbox: ${rec.facts.second_run}`);
      check(`its help: "Solution revealed: The faulty versions were shown before these cases were written", at the showing's time (${shownAt})`);
      check(`beside the first: "${rec.facts.second_compared}"`);
    }, ["real judge"], phone);

    await rec.step("History lists both runs, each opening its report", async (check) => {
      await page.goto("/history");
      for (const run of [first!, second!]) {
        const link = page.locator(`a[href="/test-design/${EXERCISE}?attempt=${run.id}"]`);
        await expect(link).toBeVisible();
      }
      const second_row = page.locator(`a[href="/test-design/${EXERCISE}?attempt=${second!.id}"]`);
      await expect(second_row).toContainText("Partly comparable with the one before");
      await expect(page.locator(`a[href="/test-design/${EXERCISE}?attempt=${first!.id}"]`)).toContainText("Not compared: the first judged run of this exercise");
      rec.facts.history_second_row = (await second_row.innerText()).split(/\s*\n+\s*/).filter(Boolean).join(" / ");
      await fitsBothWidths(page, "History", fitted);
      await page.locator(`a[href="/test-design/${EXERCISE}?attempt=${first!.id}"]`).click();
      await expect(report).toContainText("Not compared: the first judged run of this exercise.");
      await page.goBack();
      await second_row.click();
      await expect(page.getByRole("region", { name: "Compared with your previous attempt" })).toBeVisible();
      check(`History's row for the second run: "${rec.facts.history_second_row}"; the first's says it's the first; each opens its report`);
    }, undefined, phone);

    await rec.step("Nothing typed reached the API's log", async (check) => {
      expect(readFileSync(ACCESS_LOG, "utf8")).not.toContain(CANARY);
      check("the canary typed into the first run's case note isn't in the API's log");
      rec.facts.fitted = fitted.join(", ");
      rec.facts.axe = scanned.join(", ");
      check(`no sideways scroll at 412 or 360 px on: ${fitted.join("; ")}`);
      check(`axe found nothing, in dark and light, on: ${scanned.join("; ")}`);
    });
  } finally {
    rec.write(true);
  }
});
