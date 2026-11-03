import { http, HttpResponse, type JsonBodyType } from "msw";
import { setupServer } from "msw/node";

import type { Interview } from "@/api/types";

import { contentHandlers } from "./content";
import { exploreHandlers } from "./explore";
import { learnHandlers } from "./learn";
import { noteHandlers } from "./notes";
import { scenarioHandlers } from "./scenarios";
import { reviewFor } from "./review";
import { activityFacets, activityItems, careers, executionStatus, nurseFormats, hint, makePlan, nurseAnalytics, nurseGoals, nurseAnswer, nurseQuestions, page, problems, progress, queuedSubmission, review, tokenResponse, twoSum, user } from "./fixtures";

export const API = "http://localhost:8000";

/** Stands in for the browser's HttpOnly refresh cookie: set on sign-in, cleared on logout. */
export const cookieJar = { hasSession: false };

const signIn = <T extends JsonBodyType>(body: T, init?: ResponseInit) => { cookieJar.hasSession = true; return HttpResponse.json(body, init); };

/** The fake backend's search: topic, then every word of q in the title or summary. */
export function filterProblems<P extends { title: string; summary: string; topics: string[] }>(list: P[], params: URLSearchParams): P[] {
  const topic = params.get("topic");
  const words = (params.get("q") ?? "").toLowerCase().split(/\s+/).filter(Boolean);
  return list.filter((p) => (!topic || p.topics.includes(topic))
    && words.every((w) => `${p.title} ${p.summary}`.toLowerCase().includes(w)));
}

export const handlers = [
  ...contentHandlers,
  ...exploreHandlers,
  ...learnHandlers,
  ...noteHandlers,
  ...scenarioHandlers,
  http.get(`${API}/api/v1/careers`, () => HttpResponse.json(careers)),
  http.get(`${API}/api/v1/interviews/formats`, ({ request }) => HttpResponse.json(nurseFormats(new URL(request.url).searchParams.get("difficulty") ?? "easy"))),
  http.get(`${API}/api/v1/careers/:track/questions/counts`, ({ request }) => {
    const items = filterProblems(nurseQuestions.map((x) => ({ ...x, summary: x.prompt, topics: [] })), new URL(request.url).searchParams);
    const count = (d: string) => items.filter((x) => x.difficulty === d).length;
    return HttpResponse.json({ easy: count("easy"), medium: count("medium"), hard: count("hard") });
  }),
  http.get(`${API}/api/v1/careers/:track/questions`, ({ request }) => {
    const params = new URL(request.url).searchParams;
    const difficulty = params.get("difficulty");
    const items = filterProblems(nurseQuestions.map((x) => ({ ...x, summary: x.prompt, topics: [] })), params)
      .filter((x) => !difficulty || x.difficulty === difficulty);
    return HttpResponse.json({ ...page(items), total: items.length });
  }),
  http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json([])),
  http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json(nurseAnswer, { status: 201 })),
  http.get(`${API}/api/v1/careers/:track/questions/:id`, ({ params }) => {
    const q = nurseQuestions.find((x) => x.id === params.id);
    return q
      ? HttpResponse.json({ ...q, track: params.track, career_title: "Registered Nurse", tips: ["Use the STAR method."], rubric_labels: ["Sets the scene"] })
      : HttpResponse.json({ error: { code: "not_found", message: "Question not found", request_id: "r", details: null } }, { status: 404 });
  }),
  http.get(`${API}/api/v1/careers/:track/progress`, ({ params }) =>
    HttpResponse.json({ track: params.track, answered: 1, strong: 1, by_difficulty: { easy: 1, medium: 0, hard: 0 }, total_questions: 300 })),
  http.get(`${API}/api/v1/interviews`, () => HttpResponse.json(page([]))),
  http.get(`${API}/api/v1/problems/counts`, ({ request }) => {
    const items = filterProblems(problems, new URL(request.url).searchParams);
    const count = (d: string) => items.filter((p) => p.difficulty === d).length;
    return HttpResponse.json({ easy: count("easy"), medium: count("medium"), hard: count("hard") });
  }),
  http.get(`${API}/api/v1/problems`, ({ request }) => {
    const params = new URL(request.url).searchParams;
    const difficulty = params.get("difficulty");
    const items = filterProblems(problems, params).filter((p) => !difficulty || p.difficulty === difficulty);
    const size = Number(params.get("page_size") ?? 20);
    return HttpResponse.json({ ...page(items.slice(0, size)), total: items.length, page_size: size });
  }),
  http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({ execution_enabled: false, ai_provider: "offline", execution: executionStatus("not_configured"), guest_retention_days: 30 })),
  http.get(`${API}/api/v1/topics`, () => HttpResponse.json([{ topic: "arrays", count: 3 }, { topic: "hash-maps", count: 1 }])),
  http.get(`${API}/api/v1/problems/two-sum`, () => HttpResponse.json(twoSum)),
  http.get(`${API}/api/v1/problems/:slug`, ({ params }) =>
    HttpResponse.json({ error: { code: "not_found", message: `Problem '${String(params.slug)}' not found`, request_id: "req-404", details: null } }, { status: 404 })),
  http.post(`${API}/api/v1/auth/login`, () => signIn(tokenResponse())),
  http.post(`${API}/api/v1/auth/register`, () => signIn(tokenResponse(), { status: 201 })),
  http.post(`${API}/api/v1/auth/guest`, () => signIn(tokenResponse({ user: { ...user, email: null, is_guest: true, display_name: "Guest" } }), { status: 201 })),
  http.post(`${API}/api/v1/auth/logout`, () => { cookieJar.hasSession = false; return new HttpResponse(null, { status: 204 }); }),
  http.post(`${API}/api/v1/auth/refresh`, () => (cookieJar.hasSession
    ? HttpResponse.json(tokenResponse())
    : HttpResponse.json({ error: { code: "invalid_refresh", message: "Please sign in again.", request_id: "r", details: null } }, { status: 401 }))),
  http.get(`${API}/api/v1/auth/me`, () => HttpResponse.json(user)),
  http.post(`${API}/api/v1/submissions`, () => HttpResponse.json(queuedSubmission, { status: 202 })),
  http.get(`${API}/api/v1/submissions/:id`, () => HttpResponse.json(queuedSubmission)),
  http.get(`${API}/api/v1/me/submissions`, () => HttpResponse.json(page([{ id: "sub-1", problem_slug: "two-sum", problem_title: "Two Sum", mode: "submit", status: "QUEUED", created_at: new Date().toISOString(), duration_ms: null }]))),
  http.post(`${API}/api/v1/ai/hint`, async ({ request }) => {
    const body = (await request.json()) as { level: 1 | 2 | 3 | 4 };
    return HttpResponse.json(hint(body.level));
  }),
  http.post(`${API}/api/v1/ai/review`, () => HttpResponse.json(review)),
  http.get(`${API}/api/v1/ai/usage`, () => HttpResponse.json({ used_today: 2, daily_limit: 50, remaining_today: 48, provider: "offline" })),
  http.get(`${API}/api/v1/me/ai-history`, () => HttpResponse.json(page([]))),
  http.get(`${API}/api/v1/me/activity`, ({ request }) => {
    const params = new URL(request.url).searchParams;
    const items = activityItems.filter((i) => (!params.get("career") || i.career === params.get("career"))
      && (!params.get("type") || i.type === params.get("type"))
      && (!params.get("q") || i.title.toLowerCase().includes(params.get("q")!.toLowerCase())));
    return HttpResponse.json({ ...page(items), total: items.length });
  }),
  http.get(`${API}/api/v1/me/activity/facets`, () => HttpResponse.json(activityFacets)),
  http.get(`${API}/api/v1/me/careers/:track/analytics`, () => HttpResponse.json(nurseAnalytics)),
  // The review is derived from whatever the test's own interview handler returns.
  http.get(`${API}/api/v1/interviews/:id/review`, async ({ params }) => {
    const res = await fetch(`${API}/api/v1/interviews/${String(params.id)}`);
    return HttpResponse.json(reviewFor((await res.json()) as Interview));
  }),
  http.get(`${API}/api/v1/me/reviews`, () => HttpResponse.json({ due: [], upcoming: [], ladder_days: [1, 3, 7, 14, 30], note: "" })),
  http.get(`${API}/api/v1/me/plan`, ({ request }) => HttpResponse.json(makePlan(Number(new URL(request.url).searchParams.get("minutes") ?? 15)))),
  http.get(`${API}/api/v1/me/goals`, () => HttpResponse.json(nurseGoals)),
  http.put(`${API}/api/v1/me/goals`, async ({ request }) => HttpResponse.json({ ...nurseGoals, ...((await request.json()) as object), saved: true })),
  http.get(`${API}/api/v1/me/resume`, () => HttpResponse.json({ interview: null, unfinished_problem: null, last_question: null })),
  http.get(`${API}/api/v1/me/progress`, () => HttpResponse.json(progress)),
  http.get(`${API}/api/v1/me/recommendations`, () => HttpResponse.json([
    { slug: "find-largest-number", title: "Find Largest Number", difficulty: "easy", topics: ["arrays"], reason: "You've submitted this once without a pass.", kind: "retry" },
  ])),
];

export const server = setupServer(...handlers);
