import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { AttemptConditions, Interview, InterviewReview } from "@/api/types";

import { nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

/** Conditions on interview-round answers (Volume 13, prompt 3; docs/ATTEMPT_CONDITIONS.md). */

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = new Date().toISOString();
const NOTE = "Only help shown in CodeCoach is recorded. Help from anywhere else isn't known, and accessibility settings such as dictation or captions are never counted as help.";

const recorded: AttemptConditions = {
  labels: ["Hint shown"], help: [{ label: "Hint shown", detail: "Lesson “SBAR handoff” read", at: now }],
  recorded_from: "2026-11-15", note: NOTE,
  round: { recorded: true, timed_minutes: 15, follow_up: "answered", ended_early: true,
    text: "A 15-minute timed mock interview; the interviewer asked a follow-up, which you answered; the round ended early." },
};
const old: AttemptConditions = {
  labels: ["Not recorded"], help: [], recorded_from: "2026-11-15", note: NOTE,
  round: { recorded: false, timed_minutes: 15, follow_up: null, ended_early: true,
    text: "A 15-minute timed mock interview; no follow-up; the round ended early." },
};

const item = (i: number, over: Partial<InterviewReview["items"][number]>): InterviewReview["items"][number] => ({
  key: `q${i}`, index: i, title: `Question ${i + 1}`, prompt: "Tell me about it.", kind: "behavioral", role: "question",
  status: "answered", asked_at: now, answer_text: "I did it.", answered_at: now, source: "typed", transcription_note: null,
  engagement: null, feedback: null, dimensions: [], retries: 0, in_review_queue: false, question_id: `e-q-${i}`, ...over,
});

const review: InterviewReview = {
  id: "iv-c", kind: "questions", track: "registered-nurse", career_title: "Registered Nurse", problem: null,
  status: "abandoned", status_label: "Ended early", completed: false, started_at: now, ended_at: now,
  elapsed_seconds: 240, time_limit_seconds: 900, notices: [],
  items: [
    item(0, { feedback: { ...nurseAnswer, id: "a-0", conditions: recorded } }),
    item(1, { feedback: { ...nurseAnswer, id: "a-1", conditions: old } }),
    item(2, { status: "not_reached", answer_text: null, answered_at: null, asked_at: null,
      conditions_note: "The round ended before this question: nothing was recorded for it." }),
  ],
  overall: [], improvements: [], evaluation_available: true, evaluator: "built-in (offline)", disclaimer: "", final_code: null,
};

const iv: Interview = {
  id: "iv-c", kind: "questions", status: "abandoned", phase: null, phase_index: 5, phase_guide: null, problem: null,
  track: "registered-nurse", career_title: "Registered Nurse", questions: [], round_summary: null,
  duration_seconds: 900, started_at: now, deadline_at: now, ended_at: now, seconds_remaining: 0,
  candidate_turns_remaining: 30, provider: "built-in (offline)", turns: [], final_code: null, evaluation: null,
};

function serve() {
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/interviews/iv-c`, () => HttpResponse.json(iv)),
    http.get(`${API}/api/v1/interviews/iv-c/review`, () => HttpResponse.json(review)),
  );
}

describe("A round's results: what help was in play for each answer", () => {
  it("one line per answer, with the round's format; older answers say not recorded", async () => {
    serve();
    renderApp("/interviews/iv-c?item=q0", { signedIn: true });
    const first = await screen.findByRole("article", { name: "1. Question 1" });
    expect(within(first).getByText(/In-app help before this answer:/).closest("p")).toHaveTextContent("In-app help before this answer: Hint shown");
    expect(first).toHaveTextContent("A 15-minute timed mock interview; the interviewer asked a follow-up, which you answered; the round ended early.");
    expect(first).not.toHaveTextContent("No in-app help recorded");
  });

  it("an answer from before rounds were recorded reads not recorded, never none", async () => {
    serve();
    renderApp("/interviews/iv-c?item=q1", { signedIn: true });
    const second = await screen.findByRole("article", { name: "2. Question 2" });
    expect(within(second).getByText(/In-app help before this answer:/).closest("p")).toHaveTextContent(
      /^In-app help before this answer: Not recorded \(for interview rounds, help is recorded from .*15.*2026\)$/);
    expect(second).not.toHaveTextContent("No in-app help recorded");
  });

  it("a question the round never reached says nothing was recorded for it", async () => {
    serve();
    renderApp("/interviews/iv-c?item=q2", { signedIn: true });
    const third = await screen.findByRole("article", { name: "3. Question 3" });
    expect(third).toHaveTextContent("The round ended before this question: nothing was recorded for it.");
    expect(within(third).queryByText(/In-app help before this answer/)).not.toBeInTheDocument();
  });
});
