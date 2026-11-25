/**
 * The judge's busy, unavailable and "still judging" answers (Volume 8, prompt 7; RECOVERY.md).
 * A refusal isn't a job: the page says what happened, keeps the code and the last result, and
 * offers the way on that fits. A wait is shown only when the server gave a credible one, is
 * counted from its deadline (a tab that slept doesn't lag), and its end sends nothing by itself.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Submission } from "@/api/types";

import { executionStatus, queuedSubmission } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const isoAgo = (ms: number) => new Date(Date.now() - ms).toISOString();
const refusal = (code: string, message: string, status: number, details: unknown = null, headers: Record<string, string> = {}) =>
  HttpResponse.json({ error: { code, message, request_id: "req-1234567890ab", details } }, { status, headers });

/** The judge as capabilities report it (counting the looks), and every POST /submissions. */
function judge(state: "ready" | "unavailable" | "not_configured" = "ready") {
  const seen = { capabilityLooks: 0, posts: [] as Record<string, unknown>[], gets: 0, state };
  server.use(
    http.get(`${API}/api/v1/capabilities`, () => {
      seen.capabilityLooks += 1;
      return HttpResponse.json({ execution_enabled: seen.state !== "not_configured", ai_provider: "offline", guest_retention_days: 30,
        execution: executionStatus(seen.state) });
    }),
  );
  return seen;
}
function replies(seen: ReturnType<typeof judge>, ...answers: (() => Response)[]) {
  server.use(http.post(`${API}/api/v1/submissions`, async ({ request }) => {
    seen.posts.push((await request.json()) as Record<string, unknown>);
    return (answers[seen.posts.length - 1] ?? answers.at(-1)!)();
  }));
}
const submitButton = () => screen.getByRole("button", { name: /^Submit/ });
const pressSubmit = async (user: ReturnType<typeof renderApp>["user"]) =>
  user.click(await screen.findByRole("button", { name: /^Submit/ }, { timeout: 3000 }));

it("a full queue with a measured wait: counted from its deadline, and its end sends nothing", async () => {
  const seen = judge();
  replies(seen, () => refusal("judge_busy", "The judge's queue is full right now, so this wasn't submitted. Nothing was saved.", 503,
    { retry_after_seconds: 30 }, { "Retry-After": "30" }));
  const { user } = renderApp("/problems/two-sum", { signedIn: true });
  await pressSubmit(user);
  expect(await screen.findByRole("alert")).toHaveTextContent("Your submission didn't go through. The judge's queue is full right now");
  expect(screen.getByText(/You can try again in (29|30) s\./)).toBeInTheDocument();
  expect(screen.getByText(/the server's suggestion for when to try again, not when your code would be judged/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Check availability" })).not.toBeInTheDocument(); // a wait was given
  expect(submitButton()).toBeDisabled();
  // The tab sleeps through the wait: no ticks arrive, the clock moves on 31 s.
  const now = Date.now();
  const clock = vi.spyOn(Date, "now").mockReturnValue(now + 31_000);
  try {
    expect(await screen.findByText("You can try again now.", {}, { timeout: 2500 })).toBeInTheDocument();
    expect(submitButton()).toBeEnabled();
    expect(seen.posts).toHaveLength(1); // nothing was sent when the wait ended
  } finally {
    clock.mockRestore();
  }
});

it("a full queue with no credible wait offers Check availability: one look, no countdown", async () => {
  const seen = judge();
  replies(seen, () => refusal("judge_busy", "The judge's queue is full right now, so this wasn't submitted. Nothing was saved.", 503));
  const { user } = renderApp("/problems/two-sum", { signedIn: true });
  await pressSubmit(user);
  await screen.findByRole("alert");
  expect(screen.queryByText(/You can try again in/)).not.toBeInTheDocument();
  const looks = seen.capabilityLooks;
  await user.click(screen.getByRole("button", { name: "Check availability" }));
  expect(await screen.findByText(/Checked at .*: the judge is ready\. You can try again\./)).toBeInTheDocument();
  expect(seen.capabilityLooks).toBe(looks + 1);
  expect(seen.posts).toHaveLength(1);
  expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled(); // deliberate, never automatic
});

it.each([
  ["a malformed value", "soon"],
  ["a value longer than a day", "500000"],
  ["an absurdly long value", "99999999999"],
])("%s gives no countdown", async (_, header) => {
  const seen = judge();
  replies(seen, () => refusal("judge_busy", "The judge's queue is full right now.", 503, null, { "Retry-After": header }));
  const { user } = renderApp("/problems/two-sum", { signedIn: true });
  await pressSubmit(user);
  await screen.findByRole("alert");
  expect(screen.queryByText(/You can try again in/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Check availability" })).toBeInTheDocument();
  expect(submitButton()).toBeEnabled();
});

it("an HTTP-date wait is read against the server's clock, not this device's", async () => {
  // The server's clock is 10 minutes behind this device's: its date says 90 s from its own now.
  const serverNow = Date.now() - 10 * 60_000;
  const seen = judge();
  replies(seen, () => refusal("rate_limited", "You're submitting very quickly.", 429, null, {
    "Retry-After": new Date(serverNow + 90_000).toUTCString(), Date: new Date(serverNow).toUTCString(),
  }));
  const { user } = renderApp("/problems/two-sum", { signedIn: true });
  await pressSubmit(user);
  expect(await screen.findByText(/You can try again in 1 min (2\d|30) s\./)).toBeInTheDocument();
});

it("another refusal after the wait starts a new countdown from its own deadline", async () => {
  const seen = judge();
  replies(seen,
    () => refusal("rate_limited", "You're submitting very quickly.", 429, { retry_after_seconds: 2 }, { "Retry-After": "2" }),
    () => refusal("rate_limited", "You're submitting very quickly.", 429, { retry_after_seconds: 40 }, { "Retry-After": "40" }));
  const { user } = renderApp("/problems/two-sum", { signedIn: true });
  await pressSubmit(user);
  const again = await screen.findByRole("button", { name: "Try again" });
  await waitFor(() => expect(again).toBeEnabled(), { timeout: 3500 });
  await user.click(again);
  expect(await screen.findByText(/You can try again in (39|40) s\./)).toBeInTheDocument();
  expect(seen.posts).toHaveLength(2);
  // A refusal made nothing and used no key up (backend: test_judge_admission.py), so the retry is
  // simply the same code sent again.
  expect(seen.posts[1]!.source_code).toBe(seen.posts[0]!.source_code);
});

it("still being judged leads back to that submission instead of offering another submit", async () => {
  const seen = judge();
  const pending: Submission = { ...queuedSubmission, id: "sub-pending", status: "RUNNING", execution_enabled: true, created_at: isoAgo(20_000) };
  server.use(http.get(`${API}/api/v1/submissions/:id`, ({ params }) => {
    seen.gets += 1;
    return HttpResponse.json(params.id === "sub-pending" ? pending : queuedSubmission);
  }));
  replies(seen, () => refusal("submission_pending", "Your previous submission is still being judged.", 429,
    { max_pending: 1, pending_submission_id: "sub-pending", problem_slug: "two-sum", mode: "submit" }));
  const { user } = renderApp("/problems/two-sum", { signedIn: true });
  await pressSubmit(user);
  expect(await screen.findByRole("alert")).toHaveTextContent("Your previous submission is still being judged.");
  expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Show its status" }));
  const results = screen.getByRole("region", { name: "Submission results" });
  expect(await within(results).findByText("Running your code against the tests…")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(seen.posts).toHaveLength(1);
});

it("code can't run on this server: no Try again, but Save attempt, the coach, and Copy code", async () => {
  const seen = judge(); // the page still thinks Run is available; the server says otherwise
  replies(seen,
    () => refusal("execution_disabled", "Running code isn't available on this deployment. Submit to save your attempt.", 503),
    () => HttpResponse.json({ ...queuedSubmission, id: "sub-saved" }, { status: 202 }));
  const { user } = renderApp("/problems/two-sum", { signedIn: true }); // (user-event provides the clipboard)
  await user.click(await screen.findByRole("button", { name: "Run" }, { timeout: 3000 }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Your run didn't go through.");
  expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ask the coach for a review" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Copy code" }));
  expect(await screen.findByText("Copied.")).toBeInTheDocument();
  expect(await navigator.clipboard.readText()).toContain("class Solution");
  await user.click(screen.getByRole("button", { name: "Save attempt instead" }));
  await waitFor(() => expect(seen.posts).toHaveLength(2));
  expect(seen.posts[1]).toMatchObject({ mode: "submit" });
});

it("Run while the judge is unavailable: Check availability, or submit to the queue", async () => {
  const seen = judge();
  replies(seen,
    () => refusal("judge_unavailable", "The code judge can't be reached right now. Submissions wait in the queue and are judged when it's back; Run is paused.", 503),
    () => HttpResponse.json({ ...queuedSubmission, execution_enabled: true }, { status: 202 }));
  const { user } = renderApp("/problems/two-sum", { signedIn: true });
  await user.click(await screen.findByRole("button", { name: "Run" }, { timeout: 3000 }));
  await screen.findByRole("alert");
  seen.state = "unavailable";
  await user.click(screen.getByRole("button", { name: "Check availability" }));
  expect(await screen.findByText(/Checked at .*: The code judge can't be reached right now/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Submit instead (it waits in the queue)" }));
  await waitFor(() => expect(seen.posts).toHaveLength(2));
  expect(seen.posts[1]).toMatchObject({ mode: "submit" });
});

it("a result says it's for the code that was sent once the editor has changed", async () => {
  judge();
  const judged: Submission = { ...queuedSubmission, id: "sub-done", status: "PASSED", is_terminal: true, execution_enabled: true,
    source_code: "class Solution { /* what was sent */ }" };
  server.use(
    http.post(`${API}/api/v1/submissions`, () => HttpResponse.json(judged, { status: 202 })),
    http.get(`${API}/api/v1/submissions/:id`, () => HttpResponse.json(judged)),
  );
  const { user } = renderApp("/problems/two-sum", { signedIn: true });
  await pressSubmit(user);
  expect(await screen.findByTestId("result-source")).toHaveTextContent(
    /This result is for the code as submitted .*The editor has changed since; submit again to check the current code\./);
});

it("after the page stops checking by itself, Check again reads the status once", async () => {
  const seen = judge();
  const old: Submission = { ...queuedSubmission, id: "sub-old", status: "QUEUED", execution_enabled: true, created_at: isoAgo(16 * 60_000),
    source_code: "class Solution {}" };
  server.use(
    http.post(`${API}/api/v1/submissions`, () => HttpResponse.json(old, { status: 202 })),
    http.get(`${API}/api/v1/submissions/:id`, () => { seen.gets += 1; return HttpResponse.json(old); }),
  );
  const { user } = renderApp("/problems/two-sum", { signedIn: true });
  await pressSubmit(user);
  expect(await screen.findByText(/this page stopped checking by itself/)).toBeInTheDocument();
  expect(screen.getByText(/Leaving this page doesn't stop it\./)).toBeInTheDocument();
  await waitFor(() => expect(seen.gets).toBeGreaterThan(0));
  const before = seen.gets;
  await user.click(screen.getByRole("button", { name: "Check again" }));
  await waitFor(() => expect(seen.gets).toBe(before + 1));
});
