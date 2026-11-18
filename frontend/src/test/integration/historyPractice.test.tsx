/**
 * Drills, whiteboard designs and work samples in History (Volume 16, prompt 6;
 * docs/COMPARING_ATTEMPTS.md): each attempt's row says what was practised, its result and its
 * comparison in its own page's words, and its in-app help, asked for with the rows on screen.
 */
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ActivityItem, AttemptConditions } from "@/api/types";

import { renderApp } from "../render";
import { API, server } from "../server";

const NOTE = "Only help shown in CodeCoach is recorded. Help from anywhere else isn't known, and accessibility settings such as dictation or captions are never counted as help.";
const hinted: AttemptConditions = {
  labels: ["Hint shown"], help: [{ label: "Hint shown", detail: "Lesson “STAR answers” read", at: "2026-11-16T09:00:00Z" }],
  recorded_from: "2026-11-15", note: NOTE, round: null, interview: null, unrecorded: null,
};
const row = (id: string, type: ActivityItem["type"], title: string, detail: string, href: string): ActivityItem => ({
  id: `${type}:${id}`, type, occurred_at: new Date().toISOString(), career: "registered-nurse", career_title: "Registered Nurse",
  title, detail, skills: [], status: "completed", status_label: "Completed", score: null, session_id: null,
  target: { href, attempt_id: id },
});
const rows = [
  row("d-2", "drill_attempt", "Answer with a concrete example", "3 of 4 points there · Comparable with the one before", "/drills/example"),
  row("d-1", "drill_attempt", "Answer with a concrete example", "2 of 4 points there · Not compared: the first checked attempt at this drill", "/drills/example"),
  row("w-1", "whiteboard_attempt", "Design a URL shortener", "4 of 6 points addressed · Not compared: the first checked attempt at this prompt", "/whiteboard/sd-url-shortener"),
];

describe("Drills, whiteboard designs and work samples in History", () => {
  it("lists each attempt with its result, its comparison and its in-app help", async () => {
    const asked: unknown[] = [];
    server.use(
      http.get(`${API}/api/v1/me/activity`, () => HttpResponse.json({ items: rows, total: rows.length, page: 1, page_size: 20 })),
      http.post(`${API}/api/v1/me/attempt-conditions`, async ({ request }) => {
        asked.push(await request.json());
        return HttpResponse.json({ submissions: {}, answers: {}, drill_attempts: { "d-2": hinted }, whiteboard_attempts: {} });
      }),
    );
    renderApp("/history", { signedIn: true });
    const second = (await screen.findByText(/Comparable with the one before/)).closest("a")!;
    expect(second).toHaveAttribute("href", "/drills/example");
    expect(second).toHaveTextContent("Drill");
    expect(second).toHaveTextContent("3 of 4 points there");
    await waitFor(() => expect(second).toHaveTextContent("In-app help: Hint shown"));
    const first = screen.getAllByText(/Not compared: the first checked attempt at this drill/)[0]!.closest("a")!;
    expect(first.textContent).not.toMatch(/In-app help/); // none came back for it
    expect(screen.getByText(/Not compared: the first checked attempt at this prompt/).closest("a")).toHaveTextContent("Whiteboard");
    expect(asked).toEqual([{ submission_ids: [], answer_ids: [], interview_ids: [], drill_attempt_ids: ["d-2", "d-1"], whiteboard_attempt_ids: ["w-1"] }]);
  });

  it("lists scenario runs, code reviews and sample-answer comparisons, each opening its attempt, with its help (Volume 17, prompt 2)", async () => {
    const asked: unknown[] = [];
    const more = [
      { ...row("s-1", "scenario_attempt", "Two patients at once", "In progress · version 1 · Not compared: scenario runs aren't compared with each other", "/scenarios/attempts/s-1"), status: "in_progress" as const, status_label: "In progress" },
      { ...row("r-1", "code_review_attempt", "Second largest", "1 finding · points at 1 of 2 authored defects · version 1 · Not compared: code reviews aren't compared with each other yet", "/code-reviews/attempts/r-1"), career: "coding", career_title: "Coding problems" },
      { ...row("c-1", "comparison_attempt", "Specific evidence or general claims?", "1 excerpt, 1 matching the explanation · version 1 · Not compared: readings of sample answers aren't compared with each other yet", "/compare/cmp-specific-evidence?attempt=c-1"), career: "", career_title: "" },
    ];
    server.use(
      http.get(`${API}/api/v1/me/activity`, () => HttpResponse.json({ items: more, total: more.length, page: 1, page_size: 20 })),
      http.post(`${API}/api/v1/me/attempt-conditions`, async ({ request }) => {
        asked.push(await request.json());
        return HttpResponse.json({ submissions: {}, answers: {}, scenario_attempts: { "s-1": hinted }, code_review_attempts: {}, comparison_attempts: { "c-1": hinted } });
      }),
    );
    renderApp("/history", { signedIn: true });
    const scenario = (await screen.findByText(/scenario runs aren't compared/)).closest("a")!;
    expect(scenario).toHaveAttribute("href", "/scenarios/attempts/s-1");
    expect(scenario).toHaveTextContent("Scenario");
    expect(scenario).toHaveTextContent("In progress");
    await waitFor(() => expect(scenario).toHaveTextContent("In-app help: Hint shown"));
    const review = screen.getByText(/code reviews aren't compared/).closest("a")!;
    expect(review).toHaveAttribute("href", "/code-reviews/attempts/r-1");
    expect(review).toHaveTextContent("Code review");
    expect(review.textContent).not.toMatch(/In-app help/);
    const reading = screen.getByText(/readings of sample answers/).closest("a")!;
    expect(reading).toHaveAttribute("href", "/compare/cmp-specific-evidence?attempt=c-1");
    expect(reading).toHaveTextContent("Samples compared");
    expect(reading).toHaveTextContent("In-app help: Hint shown");
    expect(asked).toEqual([{ submission_ids: [], answer_ids: [], interview_ids: [], scenario_attempt_ids: ["s-1"], code_review_attempt_ids: ["r-1"], comparison_attempt_ids: ["c-1"] }]);
  });

  it("lists test-design runs in their page's words, each opening that run, with their help (Volumes 18 and 19)", async () => {
    const asked: unknown[] = [];
    const runs = [
      { ...row("t-1", "test_design_run", "Test design: Count in Range", "2 cases · told apart 2 of 4 faulty versions · version 1 · Not compared: test-design runs aren't compared with each other yet", "/test-design/tests-count-in-range?attempt=t-1"), career: "coding", career_title: "Coding problems" },
      { ...row("t-2", "test_design_run", "Test design: Count in Range", "1 case · waiting for the judge · version 1 · Not compared: test-design runs aren't compared with each other yet", "/test-design/tests-count-in-range?attempt=t-2"), career: "coding", career_title: "Coding problems", status: "awaiting_judge" as const, status_label: "Waiting for the judge" },
    ];
    server.use(
      http.get(`${API}/api/v1/me/activity`, () => HttpResponse.json({ items: runs, total: runs.length, page: 1, page_size: 20 })),
      http.post(`${API}/api/v1/me/attempt-conditions`, async ({ request }) => {
        asked.push(await request.json());
        return HttpResponse.json({ submissions: {}, answers: {}, test_design_runs: { "t-1": { ...hinted, labels: ["Solution revealed"] } } });
      }),
    );
    renderApp("/history", { signedIn: true });
    const done = (await screen.findByText(/told apart 2 of 4 faulty versions/)).closest("a")!;
    expect(done).toHaveAttribute("href", "/test-design/tests-count-in-range?attempt=t-1");
    expect(done).toHaveTextContent("Test design");
    await waitFor(() => expect(done).toHaveTextContent("In-app help: Solution revealed"));
    const waiting = screen.getByText(/waiting for the judge/).closest("a")!;
    expect(waiting).toHaveAttribute("href", "/test-design/tests-count-in-range?attempt=t-2");
    expect(waiting).toHaveTextContent("Waiting for the judge");
    // Asked for with the rows on screen (Volume 19, prompt 3), in the one request.
    expect(asked).toEqual([{ submission_ids: [], answer_ids: [], interview_ids: [], test_design_run_ids: ["t-1", "t-2"] }]);
  });
});
