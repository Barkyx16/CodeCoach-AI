/**
 * A round's answer box must accept the next answer however quickly the previous one was saved.
 *
 * React Query tells components about a request's progress from a timer (setTimeout 0). When the
 * browser's main thread stalls (a busy CI machine, a garbage-collection pause), the server's
 * answer can be processed before that timer runs, so the page never renders "sending". The answer
 * box used to wait for that render to release its double-submit guard, so the guard stayed shut
 * and the next "Next question" / "Finish interview" click silently did nothing: same question, no
 * request, no error. The browser journey e2e/formats.spec.ts stalled exactly there.
 */
import { notifyManager } from "@tanstack/react-query";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach } from "vitest";

import type { Interview, RoundQuestion } from "@/api/types";

import { nurseAnswer, nurseQuestions, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = () => new Date().toISOString();

function round(): { get: () => Interview; calls: number[] } {
  const qs: RoundQuestion[] = nurseQuestions.slice(0, 3).map((q, index) => ({
    index, id: q.id, title: q.title, prompt: q.prompt, kind: q.kind, difficulty: q.difficulty as RoundQuestion["difficulty"],
    status: index === 0 ? "current" : "pending", answer: null, speaker: null, followup: null,
  }));
  let iv: Interview = {
    id: "round-1", kind: "questions", status: "in_progress", phase: null, phase_index: 5, phase_guide: null, problem: null,
    track: "registered-nurse", career_title: "Registered Nurse", questions: qs, round_format: null,
    round_summary: { answered: 0, skipped: 0, unanswered: 3, average_score: null, focus: [] },
    duration_seconds: 900, started_at: now(), deadline_at: new Date(Date.now() + 900_000).toISOString(), ended_at: null,
    seconds_remaining: 900, candidate_turns_remaining: 30, provider: "built-in (offline)",
    turns: [{ seq: 0, role: "interviewer", phase: null, content: qs[0]!.prompt, created_at: now(), question_index: 0, skipped: false }],
    final_code: null, evaluation: null,
  };
  const calls: number[] = [];
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/interviews/round-1`, () => HttpResponse.json(iv)),
    http.post(`${API}/api/v1/interviews/round-1/answers`, async ({ request }) => {
      const { question_index } = (await request.json()) as { question_index: number };
      calls.push(question_index);
      iv = {
        ...iv,
        questions: iv.questions.map((q) => q.index === question_index ? { ...q, status: "answered", answer: nurseAnswer }
          : q.index === question_index + 1 ? { ...q, status: "current" } : q),
      };
      return HttpResponse.json(iv);
    }),
  );
  return { get: () => iv, calls };
}

afterEach(() => {
  notifyManager.setScheduler((cb) => setTimeout(cb, 0)); // the library default
});

it("answers in a row go through even when the page never got to show 'sending'", async () => {
  // Deliver React Query's updates only after the server has already answered: what a stalled
  // main thread does. The page then sees "saved" without ever seeing "sending".
  notifyManager.setScheduler((cb) => setTimeout(cb, 150));
  const { calls } = round();
  const { user } = renderApp("/interviews/round-1", { signedIn: true });

  const box = await screen.findByLabelText("Your answer", { exact: true }, { timeout: 3000 });
  expect(screen.getByText(/QUESTION 1 OF 3/)).toBeInTheDocument();
  await user.type(box, "First answer.");
  await user.click(screen.getByRole("button", { name: "Next question" }));
  expect(await screen.findByText(/QUESTION 2 OF 3/, {}, { timeout: 3000 })).toBeInTheDocument();

  await user.type(screen.getByLabelText("Your answer", { exact: true }), "Second answer.");
  await user.click(screen.getByRole("button", { name: "Next question" }));
  expect(await screen.findByText(/QUESTION 3 OF 3/, {}, { timeout: 3000 })).toBeInTheDocument();
  expect(calls).toEqual([0, 1]);
});

it("a double click still sends an answer once", async () => {
  const { calls } = round();
  const { user } = renderApp("/interviews/round-1", { signedIn: true });
  await user.type(await screen.findByLabelText("Your answer", { exact: true }), "Only once.");
  await user.dblClick(screen.getByRole("button", { name: "Next question" }));
  expect(await screen.findByText(/QUESTION 2 OF 3/)).toBeInTheDocument();
  await waitFor(() => expect(calls).toEqual([0]));
});
