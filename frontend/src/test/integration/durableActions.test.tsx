/**
 * Uncertain actions survive a reload (Volume 8, prompt 1). The reply to a submission, a hint or a
 * new story is lost, and the page is reloaded: it asks the server what the earlier key made (a
 * read) and shows that, instead of sending again under a new key. Not arrived, couldn't check,
 * changed since, signed out and another account are each handled.
 */
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { executionStatus, hint, queuedSubmission, tokenResponse, user } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const BEA = { ...user, id: "user-bea", email: "bea@example.com", display_name: "Bea" };
const keyOf = async (request: Request) => ((await request.json()) as { client_request_id?: string }).client_request_id;
const readyJudge = () => server.use(http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({
  execution_enabled: true, ai_provider: "offline", execution: executionStatus("ready"), guest_retention_days: 30,
})));
const stored = (id = user.id) => localStorage.getItem(`codecoach.pending.v1.${id}`);

afterEach(() => localStorage.clear());

/** The first submission arrives but its reply is lost; the lookup then finds it. */
function lostSubmission() {
  const posts: (string | undefined)[] = [];
  const lookups: string[] = [];
  server.use(
    http.post(`${API}/api/v1/submissions`, async ({ request }) => {
      posts.push(await keyOf(request));
      return HttpResponse.error();
    }),
    http.get(`${API}/api/v1/me/requests/:key`, ({ params }) => {
      lookups.push(params.key as string);
      return params.key === posts[0]
        ? HttpResponse.json({ kind: "submission", state: "done", id: "sub-earlier", created_at: new Date().toISOString(), problem_slug: "two-sum" })
        : HttpResponse.json({ error: { code: "request_not_found", message: "no record", request_id: "r" } }, { status: 404 });
    }),
    http.get(`${API}/api/v1/submissions/sub-earlier`, () => HttpResponse.json({
      ...queuedSubmission, id: "sub-earlier", execution_enabled: true, is_terminal: true, status: "PASSED", status_detail: "All tests passed.",
      result: { runtime_ms: 3, memory_kb: null, passed_count: 7, total_count: 7, hidden_passed: 4, hidden_total: 4, stderr_excerpt: null,
        public_results: [{ index: 0, passed: true, input: { nums: [2, 7, 11, 15], target: 9 }, expected_output: [0, 1],
          actual_output: [0, 1], exception: null, exception_message: null, missing: false, runtime_ms: 0.4 }] },
    })),
  );
  return { posts, lookups };
}

it("a submission whose reply was lost is found after a reload, not sent again", async () => {
  readyJudge();
  const srv = lostSubmission();
  const first = renderApp("/problems/two-sum", { signedIn: true });
  await first.user.click(await screen.findByRole("button", { name: /^Submit/ }, { timeout: 3000 }));
  expect(await screen.findByText(/We couldn't confirm your submission/)).toBeInTheDocument();
  expect(stored()).toContain(srv.posts[0]!); // written before it was sent
  first.unmount(); // the page is reloaded

  renderApp("/problems/two-sum", { signedIn: true });
  expect(await screen.findByText(/Your submission from .* arrived\./)).toBeInTheDocument();
  expect(screen.getByText(/Its result is below\./)).toBeInTheDocument();
  expect(await screen.findByText("All tests passed. Nice work.")).toBeInTheDocument(); // the saved result
  expect(srv.lookups).toEqual([srv.posts[0]]);
  expect(srv.posts).toHaveLength(1); // nothing sent again
  expect(stored()).toBeNull(); // resolved: the next reload won't ask again
});

it("one that never arrived is said plainly, and the next submit is a new one", async () => {
  readyJudge();
  localStorage.setItem(`codecoach.pending.v1.${user.id}`, JSON.stringify({
    "submission:two-sum": { v: 1, kind: "submission", target: "two-sum", key: "never-arrived-key", fingerprint: "x", sentAt: Date.now() },
  }));
  const srv = lostSubmission();
  renderApp("/problems/two-sum", { signedIn: true });
  expect(await screen.findByText(/The submission you sent at .* never arrived\./)).toBeInTheDocument();
  expect(screen.getByText(/The server has no record of it, so nothing was made/)).toBeInTheDocument();
  expect(srv.lookups).toEqual(["never-arrived-key"]);
  expect(stored()).toBeNull();
});

it("if the server can't be asked, it says it may have arrived and offers to check again", async () => {
  readyJudge();
  localStorage.setItem(`codecoach.pending.v1.${user.id}`, JSON.stringify({
    "submission:two-sum": { v: 1, kind: "submission", target: "two-sum", key: "unknown-key-01", fingerprint: "x", sentAt: Date.now() },
  }));
  let calls = 0;
  server.use(http.get(`${API}/api/v1/me/requests/:key`, () => {
    calls += 1;
    return calls === 1 ? HttpResponse.error()
      : HttpResponse.json({ error: { code: "request_not_found", message: "no record", request_id: "r" } }, { status: 404 });
  }));
  const { user: u } = renderApp("/problems/two-sum", { signedIn: true });
  expect(await screen.findByText(/Couldn't check the submission you sent at/)).toBeInTheDocument();
  expect(screen.getByText(/The code in the editor has changed since you sent it/)).toBeInTheDocument();
  expect(stored()).not.toBeNull(); // kept until it can be checked
  await u.click(screen.getByRole("button", { name: "Check again" }));
  expect(await screen.findByText(/never arrived/)).toBeInTheDocument();
});

it("a hint whose reply was lost is found after a reload, and the budget isn't used twice", async () => {
  const posts: (string | undefined)[] = [];
  server.use(
    http.post(`${API}/api/v1/ai/hint`, async ({ request }) => {
      posts.push(await keyOf(request));
      return HttpResponse.error();
    }),
    http.get(`${API}/api/v1/me/requests/:key`, () => HttpResponse.json({
      kind: "hint", state: "done", id: "ai-1", created_at: new Date().toISOString(), problem_slug: "two-sum", hint_level: 1,
    })),
    http.get(`${API}/api/v1/me/ai-history`, () => HttpResponse.json({
      items: posts.length ? [{ id: "ai-1", problem_slug: "two-sum", problem_title: "Two Sum", action: "hint", hint_level: 1, provider: "offline",
        created_at: new Date().toISOString(), response: hint(1).content }] : [],
      total: posts.length ? 1 : 0, page: 1, page_size: 50,
    })),
  );
  const first = renderApp("/problems/two-sum", { signedIn: true });
  await first.user.click(await screen.findByRole("button", { name: "Get a hint" }, { timeout: 3000 }));
  expect(await screen.findByText(/The hint didn't go through/)).toBeInTheDocument();
  first.unmount();

  renderApp("/problems/two-sum", { signedIn: true });
  expect(await screen.findByText(/Your hint request from .* arrived\./)).toBeInTheDocument();
  expect(screen.getByText(/The level 1 hint is below\. It wasn't asked for again\./)).toBeInTheDocument();
  expect(await screen.findByText("Hint text for level 1")).toBeInTheDocument();
  expect(posts).toHaveLength(1);
});

it("a new story whose reply was lost is found after a reload: saved once, with a link to it", async () => {
  const posts: (string | undefined)[] = [];
  server.use(
    http.post(`${API}/api/v1/me/stories`, async ({ request }) => {
      posts.push(await keyOf(request));
      return HttpResponse.error();
    }),
    http.get(`${API}/api/v1/me/requests/:key`, () => HttpResponse.json({
      kind: "story", state: "done", id: "story-earlier", created_at: new Date().toISOString(),
    })),
  );
  const first = renderApp("/stories/new", { signedIn: true });
  await first.user.type(await screen.findByLabelText(/Title/), "Calmed a busy ward");
  await first.user.click(screen.getByRole("button", { name: /^Save/ }));
  await waitFor(() => expect(posts).toHaveLength(1));
  first.unmount();

  renderApp("/stories/new", { signedIn: true });
  expect(await screen.findByText(/Your story from .* arrived\./)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open the saved story" })).toHaveAttribute("href", "/stories/story-earlier");
  expect(posts).toHaveLength(1);
});

it("signing out removes the record, and another account never checks it", async () => {
  readyJudge();
  const srv = lostSubmission();
  const first = renderApp("/problems/two-sum", { signedIn: true });
  await first.user.click(await screen.findByRole("button", { name: /^Submit/ }, { timeout: 3000 }));
  await screen.findByText(/We couldn't confirm your submission/);
  expect(stored()).not.toBeNull();
  // Another account on this device: it never sees or checks Ada's record.
  first.unmount();
  server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: BEA, access_token: "bea-token" }))));
  const bea = renderApp("/problems/two-sum", { signedIn: true });
  await screen.findByRole("button", { name: /^Submit/ }, { timeout: 3000 });
  expect(srv.lookups).toEqual([]);
  expect(stored()).not.toBeNull(); // still Ada's, for Ada
  bea.unmount();
  // Ada signs out on purpose: her record goes. (The server can't be asked here, so nothing but the
  // sign-out could remove it.)
  server.resetHandlers();
  readyJudge();
  server.use(http.get(`${API}/api/v1/me/requests/:key`, () => HttpResponse.error()));
  const again = renderApp("/problems/two-sum", { signedIn: true });
  expect(await screen.findByText(/Couldn't check the submission you sent at/, {}, { timeout: 3000 })).toBeInTheDocument();
  expect(stored()).not.toBeNull();
  await again.user.click(screen.getByRole("button", { name: "Sign out" }));
  await waitFor(() => expect(stored()).toBeNull());
});
