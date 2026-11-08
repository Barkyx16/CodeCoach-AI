/**
 * Interviews continue across tabs and devices. The server decides what happened (one interview
 * in progress, one answer per question, one reply per message); the page explains it and never
 * loses the learner's text:
 * - a start page names the interview in progress (what, how far, time left, last activity);
 * - a Start refused because another device started one shows that interview, not an error;
 * - a coding message from a tab that fell behind is refused, kept in the box, and the latest
 *   transcript loads;
 * - a message whose response was lost is found in the transcript, not sent again;
 * - a round answer refused because the question was answered elsewhere stays on screen;
 * - "End early" ends the assessed interview; "Leave for now" doesn't.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Interview, InterviewSummary, RoundQuestion } from "@/api/types";
import { roundDraftKey } from "@/features/interview/roundDrafts";

import { nurseAnswer, nurseQuestions, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const now = () => new Date().toISOString();

const liveRound: InterviewSummary = {
  id: "iv-7", kind: "questions", status: "in_progress", problem: null, track: "registered-nurse",
  career_title: "Registered Nurse", started_at: now(), ended_at: null, overall: null, average_score: null,
  progress_done: 2, progress_total: 5, seconds_remaining: 600, last_activity_at: now(),
};

const coding = (turns: Interview["turns"]): Interview => ({
  id: "iv-1", kind: "coding", questions: [], status: "in_progress", phase: "clarify", phase_index: 0,
  phase_guide: "Restate the problem and ask clarifying questions about inputs, outputs and edge cases.",
  problem: { slug: "two-sum", title: "Two Sum", difficulty: "easy" },
  duration_seconds: 1800, started_at: now(), deadline_at: new Date(Date.now() + 1800_000).toISOString(), ended_at: null,
  seconds_remaining: 1800, candidate_turns_remaining: 30, provider: "offline", turns, final_code: null, evaluation: null,
});
const opening: Interview["turns"][number] = { seq: 0, role: "interviewer", phase: "clarify", content: "Hi! Tell me how you understand the problem.", created_at: now(), skipped: false };
const turn = (seq: number, role: "candidate" | "interviewer", content: string): Interview["turns"][number] =>
  ({ seq, role, phase: "clarify", content, created_at: now(), skipped: false });

describe("Resuming an interview from another tab or device", () => {
  it("the start page says which interview is in progress, how far along, and the time left", async () => {
    server.use(http.get(`${API}/api/v1/interviews`, () => HttpResponse.json({ items: [liveRound], total: 1, page: 1, page_size: 5 })));
    renderApp("/interviews", { signedIn: true });
    const resume = await screen.findByRole("link", { name: "Resume it" });
    expect(resume).toHaveAttribute("href", "/interviews/iv-7");
    const card = resume.closest("[role=status]") as HTMLElement;
    expect(card).toHaveTextContent("Registered Nurse interview · 2 of 5 questions done · 10:00 left · last active");
    expect(screen.getByRole("button", { name: /Start interview/ })).toBeDisabled();
  });

  it("a Start refused because another device started one shows that interview, not an error", async () => {
    const other: InterviewSummary = {
      ...liveRound, id: "iv-8", kind: "coding", problem: { slug: "two-sum", title: "Two Sum", difficulty: "easy" },
      track: null, career_title: null, progress_done: 3, progress_total: null, seconds_remaining: 1200,
    };
    server.use(
      http.get(`${API}/api/v1/interviews`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
      http.post(`${API}/api/v1/interviews`, () => HttpResponse.json({ error: { code: "interview_in_progress",
        message: "You already have an interview in progress.", request_id: null,
        details: { interview_id: "iv-8", interview: other } } }, { status: 409 })),
    );
    const { user } = renderApp("/interviews", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Start interview" }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByRole("link", { name: "Resume it" })).toHaveAttribute("href", "/interviews/iv-8");
    expect(alert).toHaveTextContent("Two Sum coding interview · 3 messages sent · 20:00 left");
  });
});

describe("A coding interview open in two tabs", () => {
  it("a message from a tab that fell behind keeps its text, says why, and loads the latest", async () => {
    let current = coding([opening]);
    const posted: Record<string, unknown>[] = [];
    server.use(
      http.get(`${API}/api/v1/interviews`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
      http.get(`${API}/api/v1/interviews/iv-1`, () => HttpResponse.json(current)),
      http.post(`${API}/api/v1/interviews/iv-1/messages`, async ({ request }) => {
        posted.push((await request.json()) as Record<string, unknown>);
        // Meanwhile the other tab sent a message and got a reply.
        current = coding([opening, turn(1, "candidate", "From the other tab"), turn(2, "interviewer", "Reply to the other tab")]);
        return HttpResponse.json({ error: { code: "interview_advanced", message: "This interview moved on in another tab or on another device.",
          request_id: null, details: { turns: 3, status: "in_progress" } } }, { status: 409 });
      }),
    );
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    const box = await screen.findByLabelText("Your answer", { exact: true }, { timeout: 3000 });
    await user.type(box, "My message from this tab");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Reply to the other tab")).toBeInTheDocument(); // the latest loaded
    expect(screen.getByText(/moved on in another tab or on another device/)).toBeInTheDocument();
    expect(screen.getByLabelText("Your answer", { exact: true })).toHaveValue("My message from this tab"); // kept
    expect(posted[0]).toMatchObject({ message: "My message from this tab", after_seq: 1 });
    expect(String(posted[0]!.client_request_id)).toMatch(/^[\w-]{8,64}$/);
  });

  it("a message whose response was lost is found in the transcript, not sent again", async () => {
    let current = coding([opening]);
    let posts = 0;
    server.use(
      http.get(`${API}/api/v1/interviews`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
      http.get(`${API}/api/v1/interviews/iv-1`, () => HttpResponse.json(current)),
      http.post(`${API}/api/v1/interviews/iv-1/messages`, async ({ request }) => {
        posts += 1;
        const body = (await request.json()) as { message: string };
        current = coding([opening, turn(1, "candidate", body.message), turn(2, "interviewer", "Accepted before the line dropped")]);
        return HttpResponse.error(); // the server took it; the response never arrived
      }),
    );
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    const box = await screen.findByLabelText("Your answer", { exact: true }, { timeout: 3000 });
    await user.type(box, "Can the array be empty?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Accepted before the line dropped")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Your answer", { exact: true })).toHaveValue(""));
    expect(screen.queryByText(/Can't reach the CodeCoach server/)).not.toBeInTheDocument();
    expect(posts).toBe(1);
  });

  it("End early ends the assessed interview; Leave for now keeps it running", async () => {
    server.use(
      http.get(`${API}/api/v1/interviews`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
      http.get(`${API}/api/v1/interviews/iv-1`, () => HttpResponse.json(coding([opening]))),
    );
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    const leave = await screen.findByRole("link", { name: "Leave for now" }, { timeout: 3000 });
    expect(leave).toHaveAttribute("href", "/interviews");
    expect(screen.getByText(/the timer keeps running/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "End early" }));
    expect(confirm.mock.calls[0]![0]).toMatch(/End the interview for good.*Leave for now/s);
    confirm.mockRestore();
  });
});

describe("A question round open in two tabs", () => {
  const nurse = { ...baseUser, career_track: "registered-nurse" };

  function round(answeredElsewhere: boolean) {
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
    const advance = () => {
      iv = { ...iv, questions: iv.questions.map((q) => q.index === 0 ? { ...q, status: "answered", answer: nurseAnswer }
        : q.index === 1 ? { ...q, status: "current" } : q) };
    };
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/interviews/round-1`, () => HttpResponse.json(iv)),
      http.post(`${API}/api/v1/interviews/round-1/answers`, () => {
        advance();
        if (!answeredElsewhere) return HttpResponse.json(iv);
        return HttpResponse.json({ error: { code: "question_answered_elsewhere",
          message: "This question already has an answer: sent earlier, or from another tab or device. Your text here wasn't sent, and it's still in the box.",
          request_id: null, details: { question_index: 0, skipped: false, current_question_index: 1, status: "in_progress" } } }, { status: 409 });
      }),
    );
  }

  it("an answer from a tab that fell behind stays on screen, with a way to copy it", async () => {
    round(true);
    const { user } = renderApp("/interviews/round-1", { signedIn: true });
    const box = await screen.findByLabelText("Your answer", { exact: true }, { timeout: 3000 });
    await user.type(box, "My answer from this tab");
    await user.click(screen.getByRole("button", { name: "Next question" }));
    expect(await screen.findByText(/QUESTION 2 OF 3/, {}, { timeout: 3000 })).toBeInTheDocument(); // the round moved on
    const kept = screen.getByRole("region", { name: "Your unsent answer to question 1" });
    expect(kept).toHaveTextContent("already has an answer");
    expect(kept).toHaveTextContent("My answer from this tab");
    expect(window.localStorage.getItem(roundDraftKey("round-1", 0))).toBe("My answer from this tab"); // not lost
    await user.click(within(kept).getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("region", { name: "Your unsent answer to question 1" })).not.toBeInTheDocument();
    expect(window.localStorage.getItem(roundDraftKey("round-1", 0))).toBeNull();
  });

  it("a normal answer clears its draft and shows no notice", async () => {
    round(false);
    const { user } = renderApp("/interviews/round-1", { signedIn: true });
    const box = await screen.findByLabelText("Your answer", { exact: true }, { timeout: 3000 });
    await user.type(box, "A normal answer");
    await user.click(screen.getByRole("button", { name: "Next question" }));
    expect(await screen.findByText(/QUESTION 2 OF 3/, {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /Your unsent answer/ })).not.toBeInTheDocument();
    expect(window.localStorage.getItem(roundDraftKey("round-1", 0))).toBeNull();
  });
});
