/**
 * Conditions for debugging exercises and the coding interviewer (Volume 16, prompt 2;
 * docs/ATTEMPT_CONDITIONS.md): a coding interview's review lists the hints before it ended, in order,
 * and its format with what was checked (never help); History's interview row says the same labels; a
 * debugging attempt from before its explanation was recorded says so rather than guessing.
 */
import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { AttemptConditions, Interview, InterviewReview } from "@/api/types";

import { activityItems, queuedSubmission, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const NOTE = "Only help shown in CodeCoach is recorded. Help from anywhere else isn't known, and accessibility settings such as dictation or captions are never counted as help.";
const now = new Date().toISOString();
const interviewConditions: AttemptConditions = {
  labels: ["Hint shown"],
  help: [
    { label: "Hint shown", detail: "Level 1 hint, “Nudge”, on “Two Sum”, before the interview", at: "2026-11-16T09:00:00Z" },
    { label: "Hint shown", detail: "Level 2 hint, “Concept”, on “Two Sum”, during the interview", at: "2026-11-16T09:10:00Z" },
  ],
  recorded_from: "2026-11-14", note: NOTE, round: null, unrecorded: null,
  interview: {
    timed_minutes: 15, ending: "finished", checks_recorded: true,
    checks: [
      { what: "Message 1", detail: "checked before it was sent", at: "2026-11-16T09:05:00Z" },
      { what: "The feedback's material", detail: "checked before it was scored", at: "2026-11-16T09:14:00Z" },
    ],
    text: "A 15-minute coding interview, finished; 1 of 2 messages checked before sending; the feedback's material checked before it was scored.",
  },
};

const coding: Interview = {
  id: "iv-c", kind: "coding", status: "completed", phase: null, phase_index: 5, phase_guide: null,
  problem: { slug: "two-sum", title: "Two Sum", difficulty: "easy" }, track: null, career_title: null, questions: [], round_summary: null,
  duration_seconds: 900, started_at: now, deadline_at: now, ended_at: now, seconds_remaining: 0,
  candidate_turns_remaining: 28, provider: "built-in (offline)", turns: [], final_code: "class Solution {}", evaluation: null,
  conditions: interviewConditions,
};
const review: InterviewReview = {
  id: "iv-c", kind: "coding", track: null, career_title: null, problem: coding.problem, status: "completed", status_label: "Completed",
  completed: true, started_at: now, ended_at: now, elapsed_seconds: 840, time_limit_seconds: 900, notices: [], items: [], overall: [],
  improvements: [], evaluation_available: true, evaluator: "built-in (offline)", disclaimer: "Scores come from the built-in rubric.", final_code: "class Solution {}",
};

describe("Conditions for debugging exercises and the coding interviewer", () => {
  it("a coding interview's review lists both hints in order and what was checked, apart from help", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: baseUser }))),
      http.get(`${API}/api/v1/interviews/iv-c`, () => HttpResponse.json(coding)),
      http.get(`${API}/api/v1/interviews/iv-c/review`, () => HttpResponse.json(review)),
    );
    renderApp("/interviews/iv-c", { signedIn: true });
    const card = (await screen.findByRole("heading", { name: "In-app help before this interview" })).closest(".card") as HTMLElement;
    expect(within(card).getByText(/^In-app help before this interview:/).parentElement).toHaveTextContent("Hint shown");
    const hints = within(card).getAllByText(/^Hint shown: Level/);
    expect(hints.map((h) => h.textContent?.split(",")[0])).toEqual(["Hint shown: Level 1 hint", "Hint shown: Level 2 hint"]);
    expect(hints[0]).toHaveTextContent("“Nudge”, on “Two Sum”, before the interview");
    expect(hints[1]).toHaveTextContent("“Concept”, on “Two Sum”, during the interview");
    expect(card).toHaveTextContent("How it was given: A 15-minute coding interview, finished; 1 of 2 messages checked before sending");
    expect(card).toHaveTextContent("(the format, not help)");
    const checks = within(card).getByRole("list", { name: "Checked before it left CodeCoach" });
    expect(within(checks).getAllByRole("listitem").map((li) => li.textContent?.split(":")[0])).toEqual(["Message 1", "The feedback's material"]);
  });

  it("History's coding interview row shows the same labels, asked for with the rows on screen", async () => {
    const codingRow = {
      ...activityItems.find((i) => i.type === "interview")!,
      id: "interview:iv-c", career: "coding", career_title: "Coding", title: "Two Sum mock interview",
      target: { href: "/interviews/iv-c", interview_id: "iv-c" },
    };
    const asked: unknown[] = [];
    server.use(
      http.get(`${API}/api/v1/me/activity`, () => HttpResponse.json({ items: [codingRow], total: 1, page: 1, page_size: 20 })),
      http.post(`${API}/api/v1/me/attempt-conditions`, async ({ request }) => {
        asked.push(await request.json());
        return HttpResponse.json({ submissions: {}, answers: {}, interviews: { "iv-c": interviewConditions } });
      }),
    );
    renderApp("/history", { signedIn: true });
    const row = (await screen.findByText(/In-app help: Hint shown/)).closest("a")!;
    expect(row).toHaveTextContent("Two Sum mock interview");
    expect(asked).toEqual([{ submission_ids: [], answer_ids: [], interview_ids: ["iv-c"] }]);
  });

  it("a debugging attempt from before its explanation was recorded says so, beside the hints it did record", async () => {
    const before: AttemptConditions = {
      labels: ["Hint shown"],
      help: [{ label: "Hint shown", detail: "Level 1 hint (nudge)", at: "2026-11-15T10:00:00Z" }],
      recorded_from: "2026-11-14", note: NOTE, round: null, interview: null,
      unrecorded: "Opening the exercise's explanation and repair wasn't recorded before 16 Nov 2026, so whether it was opened before this attempt isn't known.",
    };
    server.use(http.get(`${API}/api/v1/submissions/:id`, () => HttpResponse.json({
      ...queuedSubmission, problem_slug: "debug-coldest-day", starting_code: "class Solution {}", lab_version: 1, conditions: before,
    })));
    renderApp("/history/submissions/sub-1", { signedIn: true });
    const card = (await screen.findByRole("heading", { name: "In-app help" })).closest(".card") as HTMLElement;
    expect(card).toHaveTextContent("Hint shown: Level 1 hint (nudge)");
    expect(card).toHaveTextContent("wasn't recorded before 16 Nov 2026, so whether it was opened before this attempt isn't known.");
  });
});
