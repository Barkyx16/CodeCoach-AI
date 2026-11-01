import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { hint, page, problems, progress, queuedSubmission, review, tokenResponse, twoSum, user } from "./fixtures";

export const API = "http://localhost:8000";

export const handlers = [
  http.get(`${API}/api/v1/problems`, ({ request }) => {
    const url = new URL(request.url);
    const topic = url.searchParams.get("topic");
    const difficulty = url.searchParams.get("difficulty");
    const q = url.searchParams.get("q")?.toLowerCase();
    const items = problems.filter((p) => (!topic || p.topics.includes(topic)) && (!difficulty || p.difficulty === difficulty)
      && (!q || p.title.toLowerCase().includes(q)));
    return HttpResponse.json(page(items));
  }),
  http.get(`${API}/api/v1/topics`, () => HttpResponse.json([{ topic: "arrays", count: 3 }, { topic: "hash-maps", count: 1 }])),
  http.get(`${API}/api/v1/problems/two-sum`, () => HttpResponse.json(twoSum)),
  http.get(`${API}/api/v1/problems/:slug`, ({ params }) =>
    HttpResponse.json({ error: { code: "not_found", message: `Problem '${String(params.slug)}' not found`, request_id: "req-404", details: null } }, { status: 404 })),
  http.post(`${API}/api/v1/auth/login`, () => HttpResponse.json(tokenResponse())),
  http.post(`${API}/api/v1/auth/register`, () => HttpResponse.json(tokenResponse(), { status: 201 })),
  http.post(`${API}/api/v1/auth/guest`, () => HttpResponse.json(tokenResponse({ user: { ...user, email: null, is_guest: true, display_name: "Guest" } }), { status: 201 })),
  http.post(`${API}/api/v1/auth/logout`, () => new HttpResponse(null, { status: 204 })),
  http.get(`${API}/api/v1/auth/me`, () => HttpResponse.json(user)),
  http.post(`${API}/api/v1/submissions`, () => HttpResponse.json(queuedSubmission, { status: 202 })),
  http.get(`${API}/api/v1/submissions/:id`, () => HttpResponse.json(queuedSubmission)),
  http.get(`${API}/api/v1/me/submissions`, () => HttpResponse.json(page([{ id: "sub-1", problem_slug: "two-sum", problem_title: "Two Sum", status: "QUEUED", created_at: new Date().toISOString(), duration_ms: null }]))),
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
