import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Interview, RoundQuestion } from "@/api/types";

import { nurseAnswer, nurseQuestions, panelRoles, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const now = () => new Date().toISOString();
const role = (id: string) => panelRoles.find((r) => r.id === id)!;

describe("Interview formats", () => {
  it("shows which formats fit the level, why others don't, and previews a panel without revealing questions", async () => {
    asNurse();
    let body: Record<string, unknown> = {};
    server.use(http.post(`${API}/api/v1/interviews`, async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ error: { code: "x", message: "stop here", request_id: "r", details: null } }, { status: 400 });
    }));
    const { user } = renderApp("/interviews/questions", { signedIn: true });
    const situational = await screen.findByRole("radio", { name: /Situational interview/ });
    expect(situational).toBeDisabled();
    expect(screen.getByText(/Not available: Registered Nurse has 0 Easy questions of this kind \(5 needed\)\. Try Medium or Hard\./)).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Medium" }));
    await waitFor(() => expect(screen.getByRole("radio", { name: /Situational interview/ })).toBeEnabled());
    await user.click(screen.getByRole("radio", { name: /Panel interview/ }));
    const preview = screen.getByRole("region", { name: "What to expect: Panel interview (simulated)" });
    expect(within(preview).getAllByRole("listitem").map((li) => li.textContent?.split(" asks")[0])).toEqual(
      ["Nurse manager", "Charge nurse (peer)", "Physician colleague (interdisciplinary partner)", "Charge nurse (peer)", "Nurse manager"]);
    expect(preview).toHaveTextContent("not a real employer or real people");
    expect(preview).toHaveTextContent("Up to 2 short follow-up questions");
    await user.click(screen.getByRole("button", { name: "Start interview" }));
    await waitFor(() => expect(body).toMatchObject({ kind: "questions", difficulty: "medium", format: "panel" }));
  });

  it("runs a panel: one named speaker at a time, a follow-up from that speaker, typed replies and skipping", async () => {
    asNurse();
    const qs: RoundQuestion[] = nurseQuestions.slice(0, 2).map((q, index) => ({
      index, id: q.id, title: q.title, prompt: q.prompt, kind: q.kind, difficulty: q.difficulty as RoundQuestion["difficulty"],
      status: index === 0 ? "current" : "pending", answer: null, speaker: role(index === 0 ? "hiring_manager" : "peer"), followup: null,
    }));
    const format = { id: "panel" as const, title: "Panel interview (simulated)", version: "formats v1", rubric_version: "rubric v1", roles: panelRoles, followups_used: 0, followups_max: 2, pending_followup: null };
    let iv: Interview = {
      id: "panel-1", kind: "questions", status: "in_progress", phase: null, phase_index: 5, phase_guide: null, problem: null,
      track: "registered-nurse", career_title: "Registered Nurse", questions: qs, round_format: format,
      round_summary: { answered: 0, skipped: 0, unanswered: 2, average_score: null, focus: [] },
      duration_seconds: 900, started_at: now(), deadline_at: new Date(Date.now() + 900_000).toISOString(), ended_at: null,
      seconds_remaining: 900, candidate_turns_remaining: 30, provider: "built-in (offline)",
      turns: [{ seq: 0, role: "interviewer", phase: null, content: qs[0]!.prompt, created_at: now(), question_index: 0, skipped: false }],
      final_code: null, evaluation: null,
    };
    const calls: string[] = [];
    const pending = { question_index: 0, detail: "ownership", question: "What did you personally do there, as opposed to the team?", speaker: role("hiring_manager"), status: "pending" as const };
    server.use(
      http.get(`${API}/api/v1/interviews/panel-1`, () => HttpResponse.json(iv)),
      http.post(`${API}/api/v1/interviews/panel-1/answers`, async ({ request }) => {
        calls.push(`answer:${((await request.json()) as { question_index: number }).question_index}`);
        iv = { ...iv, questions: iv.questions.map((q) => q.index === 0 ? { ...q, status: "answered", answer: nurseAnswer, followup: pending } : q),
          round_format: { ...format, followups_used: 1, pending_followup: pending } };
        return HttpResponse.json(iv);
      }),
      http.post(`${API}/api/v1/interviews/panel-1/followup`, async ({ request }) => {
        calls.push(`followup:${((await request.json()) as { answer: string }).answer}`);
        iv = { ...iv, round_format: { ...format, followups_used: 1, pending_followup: null },
          questions: iv.questions.map((q) => q.index === 0 ? { ...q, followup: { ...pending, status: "answered", answer: "I called the doctor.", covered: true } } : { ...q, status: "current" }) };
        return HttpResponse.json(iv);
      }),
    );
    const { user } = renderApp("/interviews/panel-1", { signedIn: true });
    expect(await screen.findByText("NURSE MANAGER ASKS")).toBeInTheDocument();
    expect(screen.getByText("Your turn: answer the nurse manager.")).toBeInTheDocument();
    const roster = screen.getByRole("region", { name: "Panel" });
    expect(within(roster).getByText("Nurse manager · speaking").closest("li")).toHaveAttribute("aria-current", "true");
    expect(roster).toHaveTextContent("Generic roles, not a real employer.");
    await user.type(screen.getByLabelText("Your answer", { exact: true }), "We handled it together.");
    await user.click(screen.getByRole("button", { name: "Next question" }));
    // The follow-up is the active turn, from the same speaker, named in text; focus moves to it.
    const heading = await screen.findByRole("heading", { level: 1, name: /Nurse manager asks: What did you personally do there/ });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.getByText("Your turn: reply to the nurse manager.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your reply"), "I called the doctor.");
    await user.click(screen.getByRole("button", { name: "Send reply" }));
    expect(await screen.findByText("CHARGE NURSE (PEER) ASKS")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Panel" })).getByText("Charge nurse (peer) · speaking")).toBeInTheDocument();
    expect(calls).toEqual(["answer:0", "followup:I called the doctor."]);
  });

  it("reviews show who asked, the follow-up and simulated panel perspectives", async () => {
    asNurse();
    const { reviewFor } = await import("../review");
    const base: Interview = {
      id: "panel-2", kind: "questions", status: "completed", phase: null, phase_index: 5, phase_guide: null, problem: null,
      track: "registered-nurse", career_title: "Registered Nurse",
      questions: nurseQuestions.slice(0, 1).map((q) => ({ index: 0, id: q.id, title: q.title, prompt: q.prompt, kind: q.kind, difficulty: "easy" as const, status: "answered" as const, answer: nurseAnswer })),
      round_summary: { answered: 1, skipped: 0, unanswered: 0, average_score: 92, focus: [] },
      duration_seconds: 900, started_at: now(), deadline_at: now(), ended_at: now(), seconds_remaining: 0, candidate_turns_remaining: 30,
      provider: "built-in (offline)", turns: [], final_code: null, evaluation: null,
    };
    const review = reviewFor(base);
    review.items[0] = { ...review.items[0]!, speaker: role("hiring_manager"),
      followup: { question_index: 0, detail: "result", question: "What was the outcome?", speaker: role("hiring_manager"), status: "answered", answer: "He was stable in 30 minutes.", covered: true } };
    review.perspectives = [{ role: role("hiring_manager"), asked: 1, answered: 1, average_score: 92, summary: "Focus: motivation. Average 92/100." }];
    server.use(
      http.get(`${API}/api/v1/interviews/panel-2`, () => HttpResponse.json(base)),
      http.get(`${API}/api/v1/interviews/panel-2/review`, () => HttpResponse.json(review)),
    );
    renderApp("/interviews/panel-2", { signedIn: true });
    const persp = await screen.findByRole("region", { name: "Panel perspectives (simulated)" });
    expect(persp).toHaveTextContent("Not separate human judgments");
    expect(persp).toHaveTextContent("92/100 average · 1 of 1 answered");
    expect(screen.getByText("Asked by the nurse manager (simulated role)")).toBeInTheDocument();
    expect(screen.getByText("He was stable in 30 minutes.")).toBeInTheDocument();
    expect(screen.getByText(/Your reply gave the result it asked for/)).toBeInTheDocument();
  });
});
