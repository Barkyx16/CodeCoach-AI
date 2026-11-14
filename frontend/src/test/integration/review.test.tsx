import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Comparison, Interview, InterviewReview } from "@/api/types";

import { nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = new Date().toISOString();

const iv = (over: Partial<Interview> = {}): Interview => ({
  id: "iv-r", kind: "questions", status: "abandoned", phase: null, phase_index: 5, phase_guide: null, problem: null,
  track: "registered-nurse", career_title: "Registered Nurse", questions: [], round_summary: null,
  duration_seconds: 900, started_at: now, deadline_at: now, ended_at: now, seconds_remaining: 0,
  candidate_turns_remaining: 30, provider: "built-in (offline)", turns: [], final_code: null, evaluation: null, ...over,
});

const answered = { ...nurseAnswer, id: "a-1", answer: "We handled it as a team.", score: 41, rating: "Developing" };

const roundReview: InterviewReview = {
  id: "iv-r", kind: "questions", track: "registered-nurse", career_title: "Registered Nurse", problem: null,
  status: "abandoned", status_label: "Ended early", completed: false, started_at: now, ended_at: now,
  elapsed_seconds: 240, time_limit_seconds: 900,
  notices: ["Ended early: 2 of 3 questions answered. Only answered questions have feedback."],
  items: [
    { key: "q0", index: 0, title: "Why nursing", prompt: "Why do you want to be a nurse?", kind: "motivation", role: "question",
      status: "answered", asked_at: now, answer_text: "I care about people.", answered_at: now, source: "voice",
      transcription_note: "Spoken and transcribed by your browser's speech recognition.", engagement: null,
      feedback: { ...nurseAnswer, id: "a-0", answer: "I care about people.", score: 88 },
      dimensions: [{ name: "Spoken delivery", status: "not_evaluated", summary: "Not measured: only the transcript is scored.", points: [], evidence: [] }],
      retries: 0, in_review_queue: false, question_id: "e-good-0" },
    { key: "q1", index: 1, title: "A hard shift", prompt: "Tell me about a hard shift.", kind: "behavioral", role: "question",
      status: "answered", asked_at: now, answer_text: "We handled it as a team.", answered_at: now, source: "typed",
      transcription_note: null, engagement: null, feedback: answered, dimensions: [], retries: 1, in_review_queue: false, question_id: "e-time-0" },
    { key: "q2", index: 2, title: "Triage choice", prompt: "Two patients need you at once.", kind: "situational", role: "question",
      status: "not_reached", asked_at: null, answer_text: null, answered_at: null, source: null, transcription_note: null,
      engagement: null, feedback: null, dimensions: [], retries: 0, in_review_queue: false, question_id: "m-two-0" },
  ],
  overall: [{ name: "Answer content", status: "evaluated", summary: "Average 65/100 across 2 answered questions.", points: [], evidence: [] }],
  improvements: [{
    key: "point:Explains what you personally did",
    title: "Explains what you personally did", why: "Say “I” for your own actions. Missing in 1 of 2 answers.",
    evidence: [{ item_key: "q1", label: "A hard shift", excerpt: "We handled it as a team." }],
    practice: { label: "Retry “A hard shift”", retry_index: 1, href: null },
  }],
  evaluation_available: true, evaluator: "built-in (offline)",
  disclaimer: "Scores come from the built-in rubric. The feedback is about interview communication; it isn't professional or clinical guidance.",
  final_code: null,
};

function serve(review: InterviewReview, interview: Interview = iv()) {
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/interviews/${interview.id}`, () => HttpResponse.json(interview)),
    http.get(`${API}/api/v1/interviews/${interview.id}/review`, () => HttpResponse.json(review)),
  );
}

describe("Interview review", () => {
  it("states that an abandoned interview was incomplete and links improvements to the answer that shows them", async () => {
    serve(roundReview);
    const { user, router } = renderApp("/interviews/iv-r", { signedIn: true });
    expect(await screen.findByText(/MOCK INTERVIEW · ENDED EARLY/)).toBeInTheDocument();
    expect(screen.getByText(/Ended early: 2 of 3 questions answered/)).toBeInTheDocument();
    expect(screen.getByText(/took 4 min of 15 min/)).toBeInTheDocument();
    expect(screen.getByText(/isn't professional or clinical guidance/)).toBeInTheDocument();
    // First question selected by default, with its transcription note and delivery honesty.
    expect(screen.getByRole("heading", { name: "1. Why nursing" })).toBeInTheDocument();
    expect(screen.getByText(/transcribed by your browser's speech recognition/)).toBeInTheDocument();
    // An improvement's evidence opens the exact answer it refers to.
    await user.click(screen.getByRole("button", { name: /A hard shift: “We handled it as a team.”/ }));
    expect(router.state.location.search).toBe("?item=q1");
    const detail = screen.getByRole("article", { name: "2. A hard shift" });
    expect(within(detail).getByText("We handled it as a team.")).toBeInTheDocument();
    expect(within(detail).getByRole("link", { name: "Compare 1 retry" })).toHaveAttribute("href", "/interviews/iv-r/retry/1");
    expect(screen.getByRole("link", { name: "Retry “A hard shift”" })).toHaveAttribute("href", "/interviews/iv-r/retry/1");
    // Unreached questions say so instead of showing feedback.
    await user.click(screen.getByRole("button", { name: /Triage choice/ }));
    expect(screen.getByText("Not reached: no answer, so no feedback.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Answer this question" })).toBeInTheDocument();
  });

  it("navigates questions with Previous/Next, can show all, and saves a question for review", async () => {
    let saved: unknown = null;
    serve(roundReview);
    server.use(http.post(`${API}/api/v1/me/reviews`, async ({ request }) => {
      saved = await request.json();
      return HttpResponse.json({ due: [], upcoming: [], ladder_days: [1, 3, 7, 14, 30], note: "" });
    }));
    const { user, router } = renderApp("/interviews/iv-r?item=q1", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "2. A hard shift" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(router.state.location.search).toBe("?item=q2");
    await user.click(screen.getByRole("button", { name: "Previous" }));
    await user.click(screen.getByRole("button", { name: "Save for later review" }));
    await waitFor(() => expect(saved).toEqual({ track: "registered-nurse", question_id: "e-time-0", session_id: "iv-r" }));
    expect(await screen.findByText("In your review queue")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show all" }));
    expect(screen.getAllByRole("article")).toHaveLength(3);
  });

  it("links coding feedback to the exact code line", async () => {
    const coding = iv({ id: "iv-c", kind: "coding", track: null, career_title: null, problem: { slug: "two-sum", title: "Two Sum", difficulty: "easy" }, status: "completed" });
    serve({
      ...roundReview, id: "iv-c", kind: "coding", track: null, career_title: null, status: "completed", status_label: "Completed",
      completed: true, notices: [], improvements: [], items: [], problem: coding.problem, final_code: "class Solution {\n  int[] twoSum() { return null; }\n}",
      overall: [{ name: "Technical reasoning: Code quality", status: "evaluated", summary: "2 of 4. Returns null on line 2.", points: [],
        evidence: [{ item_key: "code", label: "Line 2 of your code", excerpt: "int[] twoSum() { return null; }" }] },
        { name: "Code execution", status: "not_evaluated", summary: "Not run: code written in an interview isn't sent to the judge.", points: [], evidence: [] }],
    }, coding);
    const { user } = renderApp("/interviews/iv-c", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Interview feedback" })).toBeInTheDocument();
    expect(screen.getByText(/Not run: code written in an interview isn't sent to the judge/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Line 2 of your code/ }));
    const flagged = document.querySelector(".review-code__line.is-flagged");
    expect(flagged?.textContent).toContain("return null;");
  });
});

describe("Retry and compare", () => {
  const comparison = (over: Partial<Comparison> = {}): Comparison => ({
    question_title: "A hard shift", prompt: "Tell me about a hard shift.", original: answered, retries: [], latest: null,
    comparable: false, comparability_note: "No retry yet.", improved: [], still_missing: [], newly_missing: [], score_change: null, ...over,
  });

  it("keeps the original, sends a separate attempt, and shows what improved and what still needs work", async () => {
    let body: unknown = null;
    let current = comparison();
    const retried = { ...nurseAnswer, id: "a-2", answer: "I took charge and I called rapid response. Stable in 30 minutes.", score: 90 };
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/interviews/iv-r/questions/1/comparison`, () => HttpResponse.json(current)),
      http.post(`${API}/api/v1/interviews/iv-r/questions/1/retries`, async ({ request }) => {
        body = await request.json();
        current = comparison({
          retries: [retried], latest: retried, comparable: true, comparability_note: "Both scored by built-in (offline) · rubric v1, so the scores compare directly.",
          improved: ["Explains what you personally did"], still_missing: ["Names who you told"], newly_missing: ["Sets the scene"], score_change: 49,
        });
        return HttpResponse.json(current, { status: 201 });
      }),
    );
    const { user } = renderApp("/interviews/iv-r/retry/1", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "A hard shift" })).toBeInTheDocument();
    expect(screen.getByText(/Your original answer \(41\/100\)/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your new answer"), "I took charge and I called rapid response.");
    await user.click(screen.getByRole("button", { name: "Get feedback and compare" }));
    await waitFor(() => expect(body).toEqual({ answer: "I took charge and I called rapid response.", source: "typed" }));
    const result = await screen.findByRole("region", { name: "How your latest attempt compares" });
    expect(within(result).getByText("We handled it as a team.")).toBeInTheDocument(); // original kept
    expect(within(result).getByText(/Latest retry · 90\/100 \(\+49\)/)).toBeInTheDocument();
    expect(within(result).getByText("✓ Explains what you personally did")).toBeInTheDocument();
    expect(within(result).getByText("○ Names who you told")).toBeInTheDocument();
    expect(within(result).getByText("! Sets the scene")).toBeInTheDocument();
    expect(screen.getByLabelText("Your new answer")).toHaveValue("");
  });

  it("discloses when scores come from different evaluators", async () => {
    const latest = { ...nurseAnswer, id: "a-3", score: 70 };
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/interviews/iv-r/questions/1/comparison`, () => HttpResponse.json(comparison({
        retries: [latest], latest, comparable: false, score_change: null,
        comparability_note: "Scored by different evaluators (rubric v0 vs rubric v1), so the scores aren't directly comparable; compare the points covered instead.",
      }))),
    );
    renderApp("/interviews/iv-r/retry/1", { signedIn: true });
    expect(await screen.findByText(/aren't directly comparable/)).toBeInTheDocument();
    expect(screen.getByText("Latest retry · 70/100")).toBeInTheDocument(); // no "+N" across evaluators
  });
});

describe("Review queue", () => {
  it("explains why each question is due and supports snooze and remove", async () => {
    const calls: string[] = [];
    const item = { id: "rv-1", track: "registered-nurse", career_title: "Registered Nurse", question_id: "e-time-0", title: "A hard shift",
      href: "/careers/registered-nurse/questions/e-time-0", due_at: now, due: true, interval_days: 1, last_score: 41, reviews: 1, snoozed: false,
      why: "Due now. Last answered Nov 2 scoring 41/100 (below 70), so it comes back after 1 day." };
    const queue = (due: typeof item[]) => ({ due, upcoming: [], ladder_days: [1, 3, 7, 14, 30], note: "Nothing is emailed or pushed to you." });
    server.use(
      http.get(`${API}/api/v1/me/reviews`, () => HttpResponse.json(queue([item]))),
      http.post(`${API}/api/v1/me/reviews/rv-1/snooze`, async ({ request }) => { calls.push(`snooze:${JSON.stringify(await request.json())}`); return HttpResponse.json(queue([item])); }),
      http.delete(`${API}/api/v1/me/reviews/rv-1`, () => { calls.push("remove"); return HttpResponse.json(queue([])); }),
    );
    const { user } = renderApp("/reviews", { signedIn: true });
    const row = await screen.findByRole("listitem", { name: "A hard shift" });
    expect(within(row).getByText(/scoring 41\/100 \(below 70\)/)).toBeInTheDocument();
    expect(screen.getByText(/Nothing is emailed or pushed to you/)).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: "Answer it now" })).toHaveAttribute("href", "/careers/registered-nurse/questions/e-time-0");
    await user.click(within(row).getByRole("button", { name: "Snooze 3 days" }));
    await waitFor(() => expect(calls).toEqual(['snooze:{"days":3}']));
    await user.click(within(row).getByRole("button", { name: "Remove" }));
    expect(await screen.findByText("Nothing saved for review")).toBeInTheDocument();
  });
});
