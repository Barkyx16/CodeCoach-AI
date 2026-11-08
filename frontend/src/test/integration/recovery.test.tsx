/**
 * Failed actions become recovery choices (Volume 7, prompt 6). When a request fails, the learner
 * keeps their work and gets a clear next step next to the control that failed:
 * - an answer that never came back is sent again with the same request key, so it can't make a
 *   second submission, a second story, or a second charged AI call;
 * - a wait the server asked for (Retry-After) is counted down, and only that action waits:
 *   other controls stay usable;
 * - a refused request says why, without hiding what was already on screen (a verdict, a live
 *   interview);
 * - a session that lapses mid-work doesn't make the draft disappear.
 */
import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Interview, Submission } from "@/api/types";

import { executionStatus, hint, queuedSubmission, review, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const now = () => new Date().toISOString();
const readyJudge = () =>
  server.use(http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({
    execution_enabled: true, ai_provider: "offline", execution: executionStatus("ready"), guest_retention_days: 30,
  })));
const busy = (code: string, message: string, seconds: number, status = 429) =>
  HttpResponse.json({ error: { code, message, request_id: "req-123456789abcdef", details: { retry_after_seconds: seconds } } },
    { status, headers: { "Retry-After": String(seconds) } });
const keyOf = async (request: Request) => ((await request.json()) as { client_request_id?: string }).client_request_id;
/** The announced message of a failed action (its first sentence is in bold, the rest plain). */
const alertSaying = (text: RegExp) =>
  screen.findByText((_, el) => el?.getAttribute("role") === "alert" && text.test(el.textContent ?? ""));

describe("The workspace: Run and Submit", () => {
  it("pressing Submit again after a lost answer sends the same request, not a second submission", async () => {
    readyJudge();
    const keys: (string | undefined)[] = [];
    server.use(http.post(`${API}/api/v1/submissions`, async ({ request }) => {
      keys.push(await keyOf(request));
      return keys.length === 1 ? HttpResponse.error() : HttpResponse.json({ ...queuedSubmission, execution_enabled: true }, { status: 202 });
    }));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    const submit = await screen.findByRole("button", { name: /^Submit/ }, { timeout: 3000 });
    await user.click(submit);
    expect(await screen.findByText(/We couldn't confirm your submission/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^Submit/ })); // the main button, not "Try again"
    await waitFor(() => expect(keys).toHaveLength(2));
    expect(keys[1]).toBe(keys[0]);
  });

  it("a judge outage says so next to the buttons, keeps the last result, and refreshes the judge banner", async () => {
    readyJudge();
    let capabilityLooks = 0;
    let posts = 0;
    server.use(
      http.get(`${API}/api/v1/capabilities`, () => {
        capabilityLooks += 1;
        return HttpResponse.json({ execution_enabled: true, ai_provider: "offline", guest_retention_days: 30,
          execution: executionStatus(capabilityLooks === 1 ? "ready" : "unavailable") });
      }),
      http.post(`${API}/api/v1/submissions`, () => {
        posts += 1;
        return posts === 1
          ? HttpResponse.json({ ...queuedSubmission, id: "sub-1" }, { status: 202 })
          : HttpResponse.json({ error: { code: "judge_unavailable", message: "The code judge isn't reachable right now. Try again in a few minutes.", request_id: "r" } }, { status: 503 });
      }),
    );
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: /^Submit/ }, { timeout: 3000 }));
    const results = screen.getByRole("region", { name: "Submission results" });
    expect(await within(results).findByText("Execution results")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^Submit/ }));
    expect(await alertSaying(/^Your submission didn't go through\. The code judge isn't reachable/)).toBeInTheDocument();
    expect(within(results).getByText("Execution results")).toBeInTheDocument(); // the earlier result stays
    expect(await screen.findByText("The code judge is temporarily unavailable.")).toBeInTheDocument();
  });

  it("too many submissions: Run and Submit wait out the server's time, the coach doesn't", async () => {
    readyJudge();
    server.use(http.post(`${API}/api/v1/submissions`, () => busy("rate_limited", "Too many submissions. Wait a moment.", 45)));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: /^Submit/ }, { timeout: 3000 }));
    expect(await screen.findByText(/You can try again in 4\d s\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Submit/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Run" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Get a hint" })).toBeEnabled(); // an unrelated action
  });

  it("the wait ends, and Try again works from the keyboard", async () => {
    readyJudge();
    let posts = 0;
    server.use(http.post(`${API}/api/v1/submissions`, () => {
      posts += 1;
      return posts === 1 ? busy("server_busy", "The server is busy. Try again in a moment.", 1, 503) : HttpResponse.json(queuedSubmission, { status: 202 });
    }));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: /^Submit/ }, { timeout: 3000 }));
    const again = await screen.findByRole("button", { name: "Try again" });
    expect(again).toBeDisabled();
    await waitFor(() => expect(again).toBeEnabled(), { timeout: 3000 });
    again.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(posts).toBe(2));
  });

  it("a session that ends mid-work keeps the draft on screen", async () => {
    localStorage.setItem(`codecoach.draft.v1.${baseUser.id}.two-sum`, "class Solution { /* my work in progress */ }");
    let refreshes = 0;
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => {
        refreshes += 1;
        return refreshes === 1 ? HttpResponse.json(tokenResponse())
          : HttpResponse.json({ error: { code: "invalid_token", message: "Session expired", request_id: "r" } }, { status: 401 });
      }),
      http.post(`${API}/api/v1/ai/hint`, () => HttpResponse.json({ error: { code: "invalid_token", message: "Access token has been revoked", request_id: "r" } }, { status: 401 })),
    );
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    expect(await screen.findByText(/my work in progress/, {}, { timeout: 3000 })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Get a hint" }));
    expect(await screen.findByText(/Your session ended/)).toBeInTheDocument();
    expect(screen.getByText(/my work in progress/)).toBeInTheDocument();
    localStorage.clear();
  });
});

describe("The coach: no second charge for a lost answer", () => {
  it("a hint whose answer was lost is asked again with the same key", async () => {
    const keys: (string | undefined)[] = [];
    server.use(http.post(`${API}/api/v1/ai/hint`, async ({ request }) => {
      keys.push(await keyOf(request));
      return keys.length === 1 ? HttpResponse.error() : HttpResponse.json(hint(1));
    }));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Get a hint" }, { timeout: 3000 }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The hint didn't go through. No reply came back, so we can't tell whether it arrived. Trying again is safe: it won't be done twice.");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Hint text for level 1")).toBeInTheDocument();
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBeTruthy();
    expect(keys[1]).toBe(keys[0]);
  });

  it("a review whose answer was lost is asked again with the same key; Review again is a new one", async () => {
    const keys: (string | undefined)[] = [];
    server.use(http.post(`${API}/api/v1/ai/review`, async ({ request }) => {
      keys.push(await keyOf(request));
      return keys.length === 1 ? HttpResponse.error() : HttpResponse.json(review);
    }));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("tab", { name: "Code review" }, { timeout: 3000 }));
    await user.click(screen.getByRole("button", { name: "Review my code" }));
    await user.click(await screen.findByRole("button", { name: "Try again" }));
    await user.click(await screen.findByRole("button", { name: "Review again" }));
    await waitFor(() => expect(keys).toHaveLength(3));
    expect(keys[1]).toBe(keys[0]);
    expect(keys[2]).not.toBe(keys[0]);
  });

  it("another coaching request still running: a two-second wait, then the button is back", async () => {
    let calls = 0;
    server.use(http.post(`${API}/api/v1/ai/hint`, () => {
      calls += 1;
      return calls === 1 ? busy("ai_request_in_progress", "Your previous coaching request is still being answered.", 1) : HttpResponse.json(hint(1));
    }));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Get a hint" }, { timeout: 3000 }));
    expect(await screen.findByText(/still being answered/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Get a hint" })).toBeDisabled();
    await waitFor(() => expect(screen.getByRole("button", { name: "Get a hint" })).toBeEnabled(), { timeout: 3000 });
  });
});

describe("Other actions", () => {
  it("signing in too often: the wait is counted down and the typed details stay", async () => {
    server.use(http.post(`${API}/api/v1/auth/login`, () =>
      busy("rate_limited", "Too many attempts. Wait a minute and try again.", 50)));
    const { user } = renderApp("/login");
    await user.type(await screen.findByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await user.click(within(screen.getByRole("main")).getByRole("button", { name: "Sign in" }));
    expect(await alertSaying(/^Signing in didn't go through\. Too many attempts/)).toBeInTheDocument();
    expect(screen.getByText(/You can try again in (49|50) s\./)).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByRole("button", { name: "Sign in" })).toBeDisabled();
    expect(screen.getByLabelText("Email")).toHaveValue("ada@example.com");
    expect(screen.getByLabelText("Password")).toHaveValue("CorrectHorse42");
  });

  it("a malformed email on sign-in is marked on the field", async () => {
    server.use(http.post(`${API}/api/v1/auth/login`, () => HttpResponse.json({ error: {
      code: "validation_error", message: "Request validation failed", request_id: "r",
      details: [{ loc: ["body", "email"], msg: "value is not a valid email address" }] } }, { status: 422 })));
    const { user } = renderApp("/login");
    await user.type(await screen.findByLabelText("Email"), "ada@");
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await user.click(within(screen.getByRole("main")).getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("value is not a valid email address")).toBeInTheDocument();
    expect(screen.queryByText("Request validation failed")).not.toBeInTheDocument();
  });

  it("starting an interview with the AI budget used up says when it resets; Start waits", async () => {
    server.use(
      http.get(`${API}/api/v1/interviews`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
      http.post(`${API}/api/v1/interviews`, () => busy("rate_limited", "You've used today's AI coaching budget.", 5400)),
    );
    const { user } = renderApp("/interviews", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: /Start interview/ }));
    expect(await alertSaying(/^Starting the interview didn't go through\. You've used today's AI coaching budget\./)).toBeInTheDocument();
    expect(screen.getByText("You can try again in about 1 h 30 min.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Start interview/ })).toBeDisabled();
  });

  it("a new story whose answer was lost is saved again with the same key", async () => {
    server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: "registered-nurse" } }))));
    const keys: (string | undefined)[] = [];
    const saved = {
      id: "s-new", title: "Covering a ward", track: "registered-nurse", context: null, competencies: [], tags: [], missing: [], target: null,
      revision: 1, archived: false, practice_count: 0, preview: "", updated_at: now(), situation: "", task: "", action: "", result: "",
      reflection: "", notes: "", evidence: "", short_version: "", long_version: "", questions: [], practice: [], privacy_hints: [], created_at: now(),
    };
    server.use(http.post(`${API}/api/v1/me/stories`, async ({ request }) => {
      keys.push(await keyOf(request));
      if (keys.length === 1) return HttpResponse.error();
      return HttpResponse.json(saved, { status: 201 });
    }), http.get(`${API}/api/v1/me/stories/s-new`, () => HttpResponse.json(saved)));
    const { user, router } = renderApp("/stories/new", { signedIn: true });
    await user.type(await screen.findByLabelText("Title"), "Covering a ward");
    await user.click(screen.getByRole("button", { name: "Save story" }));
    await waitFor(() => expect(keys).toHaveLength(1));
    await user.click(screen.getByRole("button", { name: "Save story" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/stories/s-new"));
    expect(keys[0]).toBeTruthy();
    expect(keys[1]).toBe(keys[0]);
  });
});

describe("A live interview whose refresh fails", () => {
  it("stays on screen with a notice, instead of turning into an error page", async () => {
    const iv: Interview = {
      id: "iv-1", kind: "coding", questions: [], status: "in_progress", phase: "clarify", phase_index: 0,
      phase_guide: "Restate the problem.", problem: { slug: "two-sum", title: "Two Sum", difficulty: "easy" },
      duration_seconds: 1800, started_at: now(), deadline_at: new Date(Date.now() + 1800_000).toISOString(), ended_at: null,
      seconds_remaining: 1800, candidate_turns_remaining: 30, provider: "offline", final_code: null, evaluation: null,
      turns: [{ seq: 0, role: "interviewer", phase: "clarify", content: "Hi! Tell me how you understand the problem.", created_at: now(), skipped: false }],
    };
    let looks = 0;
    server.use(http.get(`${API}/api/v1/interviews/iv-1`, () => {
      looks += 1;
      return looks === 1 ? HttpResponse.json(iv) : HttpResponse.json({ error: { code: "internal_error", message: "x", request_id: "r" } }, { status: 500 });
    }));
    renderApp("/interviews/iv-1", { signedIn: true });
    expect(await screen.findByText("Hi! Tell me how you understand the problem.", {}, { timeout: 3000 })).toBeInTheDocument();
    act(() => {
      window.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("focus"));
    });
    expect(await screen.findByText(/We couldn't check this interview for updates just now/, {}, { timeout: 6000 })).toBeInTheDocument();
    expect(screen.getByText("Hi! Tell me how you understand the problem.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check again" })).toBeEnabled();
  }, 10_000);
});

// The type is used to keep the fixtures honest.
export type _Unused = Submission;
