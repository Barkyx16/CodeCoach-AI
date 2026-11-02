import { http, HttpResponse, type JsonBodyType } from "msw";
import { setupServer } from "msw/node";

import { hint, page, problems, progress, queuedSubmission, review, tokenResponse, twoSum, user } from "./fixtures";

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
  http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({ execution_enabled: false, ai_provider: "offline", guest_retention_days: 30 })),
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
  http.get(`${API}/api/v1/me/progress`, () => HttpResponse.json(progress)),
  http.get(`${API}/api/v1/me/recommendations`, () => HttpResponse.json([
    { slug: "find-largest-number", title: "Find Largest Number", difficulty: "easy", topics: ["arrays"], reason: "You've submitted this once without a pass.", kind: "retry" },
  ])),
];

export const server = setupServer(...handlers);
