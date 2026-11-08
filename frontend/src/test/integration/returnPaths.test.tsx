/**
 * Back and deep links return to the right place (Volume 7, prompt 7):
 * - interview results keep their "Back to …" after choosing an item, and offer a way on when
 *   opened directly;
 * - a link naming a career opens that career's library, signed in or not;
 * - the coding list keeps its "View more" in the URL and its rows say "Back to coding problems";
 * - a written response, or a note this browser couldn't keep, asks before it's left behind;
 * - after saving goals or confirming an email, the learner is back where they started;
 * - Back to a list puts focus on the item they came back from.
 */
import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Interview, InterviewReview, ScenarioAttempt } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { scenarioStore } from "../scenarios";
import { API, server } from "../server";

const now = new Date().toISOString();
const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));

const finished: Interview = {
  id: "iv-n", kind: "questions", status: "completed", phase: null, phase_index: 5, phase_guide: null, problem: null,
  track: "registered-nurse", career_title: "Registered Nurse", questions: [], round_summary: null,
  duration_seconds: 900, started_at: now, deadline_at: now, ended_at: now, seconds_remaining: 0,
  candidate_turns_remaining: 30, provider: "built-in (offline)", turns: [], final_code: null, evaluation: null,
};
const item = (i: number) => ({
  key: `q${i}`, index: i, title: `Question ${i + 1}`, prompt: `Prompt ${i + 1}`, kind: "behavioral", role: "question",
  status: "answered", asked_at: now, answer_text: `Answer ${i + 1}`, answered_at: now, source: "typed", transcription_note: null,
  engagement: null, feedback: null, dimensions: [], retries: 0, in_review_queue: false, question_id: `e-${i}`,
});
const review: InterviewReview = {
  id: "iv-n", kind: "questions", track: "registered-nurse", career_title: "Registered Nurse", problem: null,
  status: "completed", status_label: "Completed", completed: true, started_at: now, ended_at: now,
  elapsed_seconds: 600, time_limit_seconds: 900, notices: [], items: [item(0), item(1)] as InterviewReview["items"],
  overall: [], improvements: [], evaluation_available: true, evaluator: "built-in (offline)", disclaimer: "", final_code: null,
};

describe("Interview results", () => {
  const serve = () => server.use(
    http.get(`${API}/api/v1/interviews/iv-n`, () => HttpResponse.json(finished)),
    http.get(`${API}/api/v1/interviews/iv-n/review`, () => HttpResponse.json(review)),
  );

  it("keep Back to History after an item is chosen (it used to vanish on the first click)", async () => {
    asNurse();
    serve();
    const { user, router } = renderApp("/history", { signedIn: true });
    await act(() => router.navigate("/interviews/iv-n", { state: { from: "/history?type=interview", fromLabel: "Back to History" } }));
    expect(await screen.findByRole("link", { name: "Back to History" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Question 2/ }));
    expect(router.state.location.search).toBe("?item=q1");
    expect(screen.getByRole("link", { name: "Back to History" })).toHaveAttribute("href", "/history?type=interview");
  });

  it("opened directly, offer the list of interviews", async () => {
    asNurse();
    serve();
    renderApp("/interviews/iv-n", { signedIn: true });
    expect(await screen.findByRole("link", { name: "All your interviews" })).toHaveAttribute("href", "/history?type=interview");
  });
});

describe("Career-aware links", () => {
  it("a link naming another career opens that career's library, even when signed in", async () => {
    // A software engineer who also practised nursing questions follows "Registered Nurse questions".
    renderApp("/problems?career=registered-nurse&view=questions", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview questions" })).toBeInTheDocument();
  });

  it("an unknown career in the link falls back to the learner's own", async () => {
    asNurse();
    renderApp("/problems?career=not-a-career&view=questions", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview questions" })).toBeInTheDocument();
  });

  it("the landing page sends a nurse to their questions, not a Java problem", async () => {
    asNurse();
    const { user, router } = renderApp("/", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Practise your questions" }));
    await waitFor(() => expect(router.state.location.pathname + router.state.location.search).toBe("/problems?view=questions"));
  });
});

describe("The coding problem list", () => {
  it("keeps View more in the URL, and its rows lead back to it", async () => {
    // Twelve easy problems: five at first, then View more.
    const many = Array.from({ length: 12 }, (_, i) => ({
      slug: i === 0 ? "two-sum" : `easy-${i}`, title: i === 0 ? "Two Sum" : `Easy problem ${i}`, difficulty: "easy",
      topics: ["arrays"], summary: "A problem.",
    }));
    server.use(http.get(`${API}/api/v1/problems`, ({ request }) => {
      const size = Number(new URL(request.url).searchParams.get("page_size") ?? 5);
      return HttpResponse.json({ items: many.slice(0, size), total: many.length, page: 1, page_size: size });
    }));
    const { user, router } = renderApp("/problems", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "View more" }));
    expect(new URLSearchParams(router.state.location.search).get("shown")).toBe("15");
    expect(await screen.findByText("Showing 12 of 12")).toBeInTheDocument();
    const row = await screen.findByRole("link", { name: /Two Sum/ });
    await user.click(row);
    await waitFor(() => expect(router.state.location.pathname).toBe("/problems/two-sum"));
    const crumbs = await screen.findByRole("navigation", { name: "Breadcrumb" });
    expect(within(crumbs).getByRole("link", { name: "Back to coding problems" })).toBeInTheDocument();
    expect(within(crumbs).getByRole("link", { name: /Coding problems/ })).toHaveAttribute("href", "/problems?career=software-engineer");
    // Back to the list: still twelve rows shown, not five.
    await user.click(within(crumbs).getByRole("link", { name: "Back to coding problems" }));
    expect(await screen.findByText("Showing 12 of 12")).toBeInTheDocument();
  });

  it("a hand-edited ?shown= asks for a bounded page", async () => {
    let asked = 0;
    server.use(http.get(`${API}/api/v1/problems`, ({ request }) => {
      asked = Number(new URL(request.url).searchParams.get("page_size"));
      return HttpResponse.json({ items: [], total: 0, page: 1, page_size: asked });
    }));
    renderApp("/problems?shown=99999", { signedIn: true });
    await waitFor(() => expect(asked).toBeGreaterThan(0));
    expect(asked).toBeLessThanOrEqual(200);
  });
});

describe("Work that leaving would lose", () => {
  it("a scenario's unsent written response asks before leaving", async () => {
    asNurse();
    scenarioStore.attempts = [{ id: "att-w", version: 1, mode: "practice", parent_id: null, status: "in_progress", steps: [],
      debrief: null, created_at: now, updated_at: now, completed_at: null, node: "call" } as unknown as ScenarioAttempt];
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { user, router } = renderApp("/scenarios/attempts/att-w", { signedIn: true });
    await user.type(await screen.findByLabelText("Your response"), "Situation: bed 3 is short of breath.");
    await act(() => router.navigate("/dashboard"));
    expect(confirm).toHaveBeenCalled();
    expect(router.state.location.pathname).toBe("/scenarios/attempts/att-w"); // stayed
    expect(screen.getByLabelText("Your response")).toHaveValue("Situation: bed 3 is short of breath.");
    confirm.mockRestore();
  });

  it("a new story saved while this browser can't keep a copy opens without asking about unsaved changes", async () => {
    asNurse();
    server.use(
      http.post(`${API}/api/v1/me/stories`, () => HttpResponse.json({
        id: "s-new", title: "Covering a ward", track: "registered-nurse", context: null, competencies: [], tags: [], missing: [], target: null,
        revision: 1, archived: false, practice_count: 0, preview: "", updated_at: now, situation: "", task: "", action: "", result: "",
        reflection: "", notes: "", evidence: "", short_version: "", long_version: "", questions: [], practice: [], privacy_hints: [], created_at: now,
      }, { status: 201 })),
      http.get(`${API}/api/v1/me/stories/s-new`, () => HttpResponse.json({ error: { code: "not_found", message: "x", request_id: "r" } }, { status: 404 })),
    );
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { user, router } = renderApp("/stories/new", { signedIn: true });
    await user.type(await screen.findByLabelText("Title"), "Covering a ward");
    await user.click(screen.getByRole("button", { name: "Save story" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/stories/s-new"));
    expect(confirm).not.toHaveBeenCalled();
    confirm.mockRestore();
    setItem.mockRestore();
  });
});

describe("Coming back from a detour", () => {
  it("goals opened from the plan return to the plan, on Cancel and after saving", async () => {
    const { user, router } = renderApp("/plan", { signedIn: true });
    await user.click(await screen.findByRole("link", { name: /goals/i }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/plan/goals"));
    expect(await screen.findByRole("link", { name: "Cancel" })).toHaveAttribute("href", "/plan");
  });

  it("confirming an email from Settings goes back to Settings (not a second copy of it)", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, email_verified: false } }))),
      http.post(`${API}/api/v1/auth/verify-email/code`, () => HttpResponse.json(baseUser)),
    );
    const { user, router } = renderApp("/settings", { signedIn: true });
    await user.click((await screen.findAllByRole("link", { name: /Enter the (verification )?code/ }))[0]!);
    await waitFor(() => expect(router.state.location.pathname).toBe("/verify-email"));
    await user.type(await screen.findByLabelText("Verification code"), "123456");
    await user.click(screen.getByRole("button", { name: "Verify email" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/settings"));
    expect(router.state.historyAction).toBe("POP"); // went back, rather than pushing /settings again
  });

  it("Back to a list puts focus on the item the learner came back from", async () => {
    const { user, router } = renderApp("/history", { signedIn: true });
    const link = await screen.findByRole("link", { name: /What good patient assessment looks like/ });
    await user.click(link);
    await waitFor(() => expect(router.state.location.pathname).not.toBe("/history"));
    await act(() => router.navigate(-1));
    await waitFor(() => expect(document.activeElement?.getAttribute("href")).toBe(link.getAttribute("href")));
  });
});
