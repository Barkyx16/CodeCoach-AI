import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Interview } from "@/api/types";
import { formatClock } from "@/features/interview/useCountdown";

import { renderApp } from "../render";
import { API, server } from "../server";

const base = (): Interview => ({
  id: "iv-1", kind: "coding", questions: [], status: "in_progress", phase: "clarify", phase_index: 0,
  phase_guide: "Restate the problem and ask clarifying questions about inputs, outputs and edge cases.",
  problem: { slug: "two-sum", title: "Two Sum", difficulty: "easy" },
  duration_seconds: 1800, started_at: new Date().toISOString(),
  deadline_at: new Date(Date.now() + 1800_000).toISOString(), ended_at: null,
  seconds_remaining: 1800, candidate_turns_remaining: 30, provider: "offline",
  turns: [{ seq: 0, role: "interviewer", phase: "clarify", content: "Hi! Tell me how you understand the problem.", created_at: new Date().toISOString(), skipped: false }],
  final_code: null, evaluation: null,
});

const evaluation: Interview["evaluation"] = {
  scores: [
    { dimension: "problem_solving", score: 4, evidence: "Used a hash map in one pass." },
    { dimension: "communication", score: 3, evidence: "Explained each step." },
    { dimension: "code_quality", score: 4, evidence: "No issues found." },
    { dimension: "complexity_analysis", score: 2, evidence: "Stated O(n^2) for an O(n) solution." },
    { dimension: "testing", score: 1, evidence: "No edge cases mentioned." },
  ],
  overall: "solid", summary: "Strongest area: problem solving. Biggest opportunity: testing.",
  strengths: ["Used a hash map in one pass."], improvements: ["Walk through edge cases before finishing."], confidence: "low",
};

function liveInterviewServer() {
  let iv = base();
  const posted: unknown[] = [];
  server.use(
    http.post(`${API}/api/v1/interviews`, () => HttpResponse.json(iv, { status: 201 })),
    http.get(`${API}/api/v1/interviews`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
    http.get(`${API}/api/v1/interviews/iv-1`, () => HttpResponse.json(iv)),
    http.post(`${API}/api/v1/interviews/iv-1/messages`, async ({ request }) => {
      const body = (await request.json()) as { message: string; code: string };
      posted.push(body);
      const n = iv.turns.length;
      iv = {
        ...iv, phase: "approach", phase_index: 1, candidate_turns_remaining: iv.candidate_turns_remaining - 1,
        turns: [...iv.turns,
          { seq: n, role: "candidate", phase: "clarify", content: body.message, created_at: new Date().toISOString(), skipped: false },
          { seq: n + 1, role: "interviewer", phase: "approach", content: "Good question. How would you approach it?", created_at: new Date().toISOString(), skipped: false }],
      };
      return HttpResponse.json(iv);
    }),
    http.post(`${API}/api/v1/interviews/iv-1/finish`, () => {
      iv = { ...iv, status: "completed", phase: null, phase_index: 5, phase_guide: null, seconds_remaining: 0,
        ended_at: new Date().toISOString(), evaluation };
      return HttpResponse.json(iv);
    }),
  );
  return { posted };
}

describe("Mock interview", () => {
  it("prevents more messages after the interviewer wraps up", async () => {
    const iv = { ...base(), phase: null, phase_index: 5, candidate_turns_remaining: 0 };
    server.use(http.get(`${API}/api/v1/interviews/iv-1`, () => HttpResponse.json(iv)));
    renderApp("/interviews/iv-1", { signedIn: true });
    expect(await screen.findByLabelText("Your answer")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Finish & get feedback" })).toBeEnabled();
  });

  it("reports an editor problem-load error instead of spinning indefinitely", async () => {
    liveInterviewServer();
    server.use(http.get(`${API}/api/v1/problems/two-sum`, () => HttpResponse.json({
      error: { code: "unavailable", message: "The problem could not be loaded." },
    }, { status: 503 })));
    renderApp("/interviews/iv-1", { signedIn: true });
    expect(await screen.findByRole("alert")).toHaveTextContent("The problem could not be loaded.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
  it("starts an interview and lands in the live session", async () => {
    liveInterviewServer();
    const { user, router } = renderApp("/interviews", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Mock interview" })).toBeInTheDocument();
    await user.click(screen.getByLabelText("45 min"));
    await user.click(screen.getByRole("button", { name: "Start interview" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/interviews/iv-1"));
    expect(await screen.findByText("Hi! Tell me how you understand the problem.")).toBeInTheDocument();
    expect(screen.getByRole("timer")).toHaveTextContent(/^(30:00|29:5\d)$/);
    const stepper = screen.getByRole("list", { name: "Interview progress" });
    expect(within(stepper).getByText("Clarify").closest("li")).toHaveAttribute("aria-current", "step");
  });

  it("sends answers with the current code and shows the interviewer's reply", async () => {
    const { posted } = liveInterviewServer();
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    const box = await screen.findByLabelText("Your answer");
    await user.type(box, "Can the input be empty?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Good question. How would you approach it?")).toBeInTheDocument();
    expect(screen.getByText("Can the input be empty?")).toBeInTheDocument();
    expect(posted[0]).toMatchObject({ message: "Can the input be empty?" });
    expect((posted[0] as { code: string }).code).toContain("class Solution");
    expect(screen.getByText("29 messages left")).toBeInTheDocument();
    expect(box).toHaveValue("");
  });

  it("never shows a sent message twice while the server's copy arrives", async () => {
    // Recreates the race CI caught: the server's transcript (with the new message) lands in the
    // cache before the send call has finished. The pending bubble must give way in that render.
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    const withAnswer = (text: string): Interview => {
      const iv = base();
      return { ...iv, turns: [...iv.turns, { seq: 1, role: "candidate", phase: "clarify", content: text, created_at: new Date().toISOString(), skipped: false }] };
    };
    server.use(
      http.get(`${API}/api/v1/interviews/iv-1`, () => HttpResponse.json(base())),
      http.post(`${API}/api/v1/interviews/iv-1/messages`, async () => { await gate; return HttpResponse.json(withAnswer("Is the array sorted?")); }),
    );
    const { user, queryClient } = renderApp("/interviews/iv-1", { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Is the array sorted?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Is the array sorted?")).toBeInTheDocument(); // the pending bubble

    act(() => queryClient.setQueryData(["me", "interview", "iv-1"], withAnswer("Is the array sorted?")));
    // Query observers are notified on the next tick: wait until the server's copy is on screen.
    await waitFor(() => expect(document.querySelector(".bubble--candidate:not(.bubble--pending)")).not.toBeNull());
    expect(screen.getAllByText("Is the array sorted?")).toHaveLength(1);
    expect(screen.queryByLabelText("Interviewer is typing")).not.toBeInTheDocument();

    release();
    await waitFor(() => expect(screen.getByLabelText("Your answer")).toBeEnabled());
    expect(screen.getAllByText("Is the array sorted?")).toHaveLength(1);
  });

  it("ends early only after confirmation, and still shows feedback", async () => {
    let abandoned = 0;
    let iv = base();
    server.use(
      http.get(`${API}/api/v1/interviews/iv-1`, () => HttpResponse.json(iv)),
      http.post(`${API}/api/v1/interviews/iv-1/abandon`, () => {
        abandoned += 1;
        iv = { ...iv, status: "abandoned", phase: null, phase_guide: null, seconds_remaining: 0,
          ended_at: new Date().toISOString(), evaluation };
        return HttpResponse.json(iv);
      }),
    );
    const confirm = vi.spyOn(window, "confirm");
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    const endEarly = await screen.findByRole("button", { name: "End early" });

    confirm.mockReturnValueOnce(false); // "Cancel": nothing happens
    await user.click(endEarly);
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(abandoned).toBe(0);
    expect(screen.getByLabelText("Your answer")).toBeInTheDocument();

    confirm.mockReturnValueOnce(true); // "OK": the interview ends and feedback is shown
    await user.click(endEarly);
    expect(await screen.findByRole("heading", { name: "Interview feedback" })).toBeInTheDocument();
    expect(abandoned).toBe(1);
    confirm.mockRestore();
  });

    it("finishes and shows rubric feedback with evidence", async () => {
    liveInterviewServer();
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Finish & get feedback" }));
    expect(await screen.findByRole("heading", { name: "Interview feedback" })).toBeInTheDocument();
    expect(screen.getByText("Overall").parentElement).toHaveTextContent("Solid");
    const rubric = screen.getByRole("list", { name: /rubric scores/i });
    expect(within(rubric).getByText("Testing")).toBeInTheDocument();
    expect(within(rubric).getByRole("img", { name: "1 out of 4" })).toBeInTheDocument();
    expect(screen.getByText("Stated O(n^2) for an O(n) solution.")).toBeInTheDocument();
    expect(screen.getByText("Walk through edge cases before finishing.")).toBeInTheDocument();
  });

  it("offers to resume when an interview is already in progress", async () => {
    server.use(
      http.get(`${API}/api/v1/interviews`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
      http.post(`${API}/api/v1/interviews`, () => HttpResponse.json({ error: { code: "interview_in_progress",
        message: "You already have an interview in progress.", request_id: null, details: { interview_id: "iv-9" } } }, { status: 409 })),
    );
    const { user } = renderApp("/interviews", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Start interview" }));
    expect(await screen.findByRole("link", { name: "Resume it" })).toHaveAttribute("href", "/interviews/iv-9");
  });

  it("offers the interview in progress up front instead of a Start that can only fail", async () => {
    let posts = 0;
    server.use(
      http.get(`${API}/api/v1/interviews`, () => HttpResponse.json({ items: [{
        id: "iv-7", kind: "coding", status: "in_progress", problem: { slug: "two-sum", title: "Two Sum", difficulty: "easy" },
        started_at: new Date().toISOString(), ended_at: null, overall: null, average_score: null,
      }], total: 1, page: 1, page_size: 5 })),
      http.post(`${API}/api/v1/interviews`, () => { posts += 1; return HttpResponse.json({}, { status: 500 }); }),
    );
    renderApp("/interviews", { signedIn: true });
    const resume = await screen.findByRole("link", { name: "Resume it" });
    expect(resume).toHaveAttribute("href", "/interviews/iv-7");
    expect(resume.closest("[role=status]")).toHaveTextContent("end it there to start another");
    expect(screen.getByRole("button", { name: /Start interview/ })).toBeDisabled();
    expect(posts).toBe(0);
  });

  it("requires sign-in", async () => {
    renderApp("/interviews");
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  });

  it("formats the clock", () => {
    expect(formatClock(0)).toBe("0:00");
    expect(formatClock(65)).toBe("1:05");
    expect(formatClock(1800)).toBe("30:00");
  });
});
