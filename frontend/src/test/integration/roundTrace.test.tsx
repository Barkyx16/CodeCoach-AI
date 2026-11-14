/**
 * One round action, traced from the click to what the screen showed (docs/OBSERVABILITY.md):
 * the request carries the action's W3C trace context, and the page reports how it ended, under
 * the same trace id, to the app's own API, only when the server allows it.
 */
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, expect, it } from "vitest";

import type { Interview, RoundQuestion } from "@/api/types";
import { resetRoundScreensForTests } from "@/features/interview/roundDiag";
import { flushUiTelemetry, resetUiTelemetryForTests, telemetryStats } from "@/lib/uiTelemetry";

import { executionStatus, nurseAnswer, nurseQuestions, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = () => new Date().toISOString();
const TRACEPARENT = /^00-([0-9a-f]{32})-([0-9a-f]{16})-01$/;

interface Sent { traceparent: string | null }
interface Reported { trace_id: string; action: string; outcome: string; duration_ms: number; status: number | null }

function setup({ telemetry = true, answer }: { telemetry?: boolean; answer?: (iv: Interview) => Response | Promise<Response> } = {}) {
  const qs: RoundQuestion[] = nurseQuestions.slice(0, 3).map((q, index) => ({
    index, id: q.id, title: q.title, prompt: q.prompt, kind: q.kind, difficulty: q.difficulty as RoundQuestion["difficulty"],
    status: index === 0 ? "current" : "pending", answer: null, speaker: null, followup: null,
  }));
  let iv: Interview = {
    id: "round-t", kind: "questions", status: "in_progress", phase: null, phase_index: 5, phase_guide: null, problem: null,
    track: "registered-nurse", career_title: "Registered Nurse", questions: qs, round_format: null,
    round_summary: { answered: 0, skipped: 0, unanswered: 3, average_score: null, focus: [] },
    duration_seconds: 900, started_at: now(), deadline_at: new Date(Date.now() + 900_000).toISOString(), ended_at: null,
    seconds_remaining: 900, candidate_turns_remaining: 30, provider: "built-in (offline)",
    turns: [{ seq: 0, role: "interviewer", phase: null, content: qs[0]!.prompt, created_at: now(), question_index: 0, skipped: false }],
    final_code: null, evaluation: null,
  };
  const sent: Sent[] = [];
  const reported: Reported[] = [];
  let telemetryCalls = 0;
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({
      execution_enabled: false, ai_provider: "offline", execution: executionStatus("not_configured"), guest_retention_days: 30, ui_telemetry: telemetry,
    })),
    http.get(`${API}/api/v1/interviews/round-t`, () => HttpResponse.json(iv)),
    http.post(`${API}/api/v1/interviews/round-t/answers`, async ({ request }) => {
      sent.push({ traceparent: request.headers.get("traceparent") });
      if (answer) return answer(iv);
      const { question_index } = (await request.json()) as { question_index: number };
      iv = { ...iv, questions: iv.questions.map((q) => q.index === question_index ? { ...q, status: "answered", answer: nurseAnswer }
        : q.index === question_index + 1 ? { ...q, status: "current" } : q) };
      return HttpResponse.json(iv, { headers: { "X-Request-ID": "req-answer-0001" } });
    }),
    http.post(`${API}/api/v1/telemetry/ui`, async ({ request }) => {
      telemetryCalls += 1;
      reported.push(...((await request.json()) as { events: Reported[] }).events);
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return { sent, reported, calls: () => telemetryCalls, interview: () => iv };
}

beforeEach(() => { resetUiTelemetryForTests(); resetRoundScreensForTests(); });
afterEach(() => { resetUiTelemetryForTests(); resetRoundScreensForTests(); });

async function answerFirst() {
  const { user } = renderApp("/interviews/round-t", { signedIn: true });
  await user.type(await screen.findByLabelText("Your answer", { exact: true }), "My answer.");
  await user.click(screen.getByRole("button", { name: "Next question" }));
  return user;
}

it("an answer carries its action's trace, and the page reports it was rendered under the same trace", async () => {
  const { sent, reported } = setup();
  await answerFirst();
  expect(await screen.findByText(/QUESTION 2 OF 3/)).toBeInTheDocument();
  await waitFor(() => expect(sent).toHaveLength(1));
  const traceId = TRACEPARENT.exec(sent[0]!.traceparent ?? "")?.[1];
  expect(traceId).toBeDefined();
  await flushUiTelemetry();
  await waitFor(() => expect(reported).toHaveLength(1));
  expect(reported[0]).toMatchObject({ trace_id: traceId, action: "answer", outcome: "rendered", status: 200 });
  expect(reported[0]!.duration_ms).toBeGreaterThanOrEqual(0);
  expect(JSON.stringify(reported)).not.toContain("My answer"); // never the learner's words
});

it("no answer from the server is a network error; the answer box keeps the draft", async () => {
  const { reported } = setup({ answer: () => HttpResponse.error() });
  await answerFirst();
  expect(await screen.findByRole("alert")).toHaveTextContent(/can't reach/i);
  expect(screen.getByLabelText("Your answer", { exact: true })).toHaveValue("My answer.");
  await flushUiTelemetry();
  await waitFor(() => expect(reported).toHaveLength(1));
  expect(reported[0]).toMatchObject({ action: "answer", outcome: "network_error", status: 0 });
});

it("a server failure is reported as a server error, distinct from a refusal", async () => {
  const { reported } = setup({
    answer: () => HttpResponse.json({ error: { code: "internal_error", message: "Something went wrong", request_id: "req-500-000001", details: null } }, { status: 500 }),
  });
  await answerFirst();
  await screen.findByRole("alert");
  await flushUiTelemetry();
  await waitFor(() => expect(reported).toHaveLength(1));
  expect(reported[0]).toMatchObject({ outcome: "server_error", status: 500, error_code: "internal_error", request_id: "req-500-000001" });
});

it("a saved answer the screen never shows is reported as not rendered", async () => {
  // The server answers 200 but with the round unchanged (as if a stale copy came back).
  const { reported } = setup({ answer: (iv) => HttpResponse.json(iv) });
  await answerFirst();
  await flushUiTelemetry();
  await waitFor(() => expect(reported).toHaveLength(1), { timeout: 8000 });
  expect(reported[0]).toMatchObject({ outcome: "not_rendered", status: 200 });
  expect(reported[0]!.duration_ms).toBeGreaterThanOrEqual(5000);
}, 15_000);

it("nothing is reported when the server doesn't allow it", async () => {
  const { reported, calls } = setup({ telemetry: false });
  await answerFirst();
  expect(await screen.findByText(/QUESTION 2 OF 3/)).toBeInTheDocument();
  await flushUiTelemetry();
  expect(calls()).toBe(0);
  expect(reported).toHaveLength(0);
});

it("a failing telemetry endpoint is dropped, not retried, and never signs the learner out", async () => {
  setup();
  let refreshes = 0;
  let telemetryCalls = 0;
  server.use(
    http.post(`${API}/api/v1/telemetry/ui`, () => {
      telemetryCalls += 1;
      return HttpResponse.json({ error: { code: "unauthorized", message: "no", request_id: "r", details: null } }, { status: 401 });
    }),
  );
  await answerFirst();
  expect(await screen.findByText(/QUESTION 2 OF 3/)).toBeInTheDocument();
  server.use(http.post(`${API}/api/v1/auth/refresh`, () => { refreshes += 1; return HttpResponse.json(tokenResponse({ user: nurse })); }));
  await waitFor(async () => { await flushUiTelemetry(); expect(telemetryCalls).toBe(1); });
  await flushUiTelemetry();
  await new Promise((r) => setTimeout(r, 50));
  expect(telemetryCalls).toBe(1); // dropped, not retried
  expect(refreshes).toBe(0); // a telemetry 401 doesn't touch the session
  expect(telemetryStats.failedBatches).toBe(1);
  expect(screen.getByText(/QUESTION 2 OF 3/)).toBeInTheDocument(); // still practising, still signed in
});
