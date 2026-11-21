/**
 * A reviewed follow-up coding problem (Volume 14, prompt 10; docs/FOLLOW_UPS.md, "Coding
 * problems"): offered under a passed submission (at phone size, in the Code tab), with what the two
 * share and how they differ; "Not now" asks the server, so it stays dismissed everywhere; opened
 * from the offer, the first submission carries the link and says its verdict is its own; follow-ups
 * submitted are listed with their own verdicts, never combined.
 */
import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ProblemFollowUpsOut, Submission, SubmissionCreate } from "@/api/types";

import { executionStatus, queuedSubmission, twoSum } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const MESSAGE = "An optional, different problem that shares one idea with this one. Its verdict will be its own: it isn't combined with this one's, and passing it doesn't by itself show that anything was learned.";
const offered: ProblemFollowUpsOut = {
  status: "offered", message: MESSAGE, answered: [],
  offers: [{
    slug: "two-sum-sorted", title: "Two Sum in a Sorted Array", difficulty: "EASY",
    shares: "Finding the two values that add up to a target", difference: "The array is sorted, so two pointers replace the lookup table",
    exposure: "Not previously attempted in this app", from_submission_id: "sub-1",
  }],
};
const done: ProblemFollowUpsOut = {
  status: "done", message: "The related problems for this one were attempted or dismissed.", offers: [],
  answered: [{ submission_id: "sub-9", slug: "two-sum-sorted", title: "Two Sum in a Sorted Array", status: "FAILED", passed_count: 1, total_count: 6, created_at: "2026-11-15T09:00:00Z", follows_up_submission_id: "sub-1" }],
};
const passed = (over: Partial<Submission> = {}): Submission => ({
  ...queuedSubmission, status: "PASSED", status_detail: "All tests passed.", is_terminal: true, execution_enabled: true,
  result: { runtime_ms: 1, memory_kb: null, passed_count: 7, total_count: 7, hidden_passed: 4, hidden_total: 4, stderr_excerpt: null, public_results: [] },
  compared: null, ...over,
});
const ready = http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({ execution_enabled: true, ai_provider: "offline", execution: executionStatus("ready", null), guest_retention_days: 30 }));

const sorted = http.get(`${API}/api/v1/problems/two-sum-sorted`, () => HttpResponse.json({ ...twoSum, slug: "two-sum-sorted", title: "Two Sum in a Sorted Array" }));

function judgedOnSubmit(sub: Submission, sent: SubmissionCreate[] = []) {
  return [
    ready, sorted,
    http.post(`${API}/api/v1/submissions`, async ({ request }) => {
      sent.push((await request.json()) as SubmissionCreate);
      return HttpResponse.json(sub, { status: 202 });
    }),
    http.get(`${API}/api/v1/submissions/${sub.id}`, () => HttpResponse.json(sub)),
  ];
}

const realMatchMedia = window.matchMedia;
afterEach(() => { window.matchMedia = realMatchMedia; });

describe("A related coding problem", () => {
  it("is offered under a passed submission, with what's the same and what's different, and Not now asks the server", async () => {
    let state = offered;
    const dismissed: string[] = [];
    server.use(
      ...judgedOnSubmit(passed()),
      http.get(`${API}/api/v1/problems/two-sum/follow-ups`, () => HttpResponse.json(state)),
      http.post(`${API}/api/v1/problems/two-sum/follow-ups/:to/dismiss`, ({ params }) => {
        dismissed.push(String(params.to));
        state = { ...offered, status: "done", offers: [], message: "The related problems for this one were attempted or dismissed." };
        return HttpResponse.json(state);
      }),
    );
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: /^Submit/ }, { timeout: 4000 }));
    const results = await screen.findByRole("region", { name: "Submission results" });
    const box = await within(results).findByRole("region", { name: "A related problem" }, { timeout: 3000 });
    expect(within(box).getByRole("link", { name: "Two Sum in a Sorted Array" })).toHaveAttribute("href", "/problems/two-sum-sorted?followUpOf=sub-1");
    expect(box).toHaveTextContent("The same: Finding the two values that add up to a target");
    expect(box).toHaveTextContent("Different: The array is sorted, so two pointers replace the lookup table");
    expect(box).toHaveTextContent("Not previously attempted in this app.");
    expect(box).toHaveTextContent(MESSAGE);
    expect(box.textContent).not.toMatch(/mastered|improved|new to you/i);
    // Shown once: not also beside the problem while it's under the result.
    expect(screen.getAllByRole("region", { name: "A related problem" })).toHaveLength(1);
    await user.click(within(box).getByRole("button", { name: "Not now: Two Sum in a Sorted Array" }));
    expect(dismissed).toEqual(["two-sum-sorted"]);
    await expect.poll(() => screen.queryByRole("region", { name: "A related problem" })).toBeNull();
  });

  it("isn't put under a failed result; one offered after an earlier pass stays beside the problem", async () => {
    server.use(
      ...judgedOnSubmit(passed({ status: "FAILED", status_detail: "Some tests failed." })),
      http.get(`${API}/api/v1/problems/two-sum/follow-ups`, () => HttpResponse.json(offered)),
    );
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: /^Submit/ }, { timeout: 4000 }));
    await screen.findByText("Some tests failed. Check the cases below.");
    const results = screen.getByRole("region", { name: "Submission results" });
    const statement = screen.getByRole("region", { name: "Problem description" });
    expect(await within(statement).findByRole("region", { name: "A related problem" })).toBeInTheDocument();
    expect(within(results).queryByRole("region", { name: "A related problem" })).not.toBeInTheDocument();
  });

  it("opened from the offer, the first submission carries the link and says its verdict is its own", async () => {
    const sent: SubmissionCreate[] = [];
    const follow = passed({
      id: "sub-9", problem_slug: "two-sum-sorted", status: "FAILED", status_detail: "Some tests failed.",
      follows_up: { submission_id: "sub-1", problem_slug: "two-sum", problem_title: "Two Sum", status: "PASSED", text: "A follow-up to Two Sum, a different problem. Its own verdict, not combined with that problem's or compared with it." },
    });
    server.use(...judgedOnSubmit(follow, sent));
    const { user } = renderApp("/problems/two-sum-sorted?followUpOf=sub-1", { signedIn: true });
    const banner = await screen.findByRole("region", { name: "A follow-up problem" }, { timeout: 4000 });
    expect(banner).toHaveTextContent("your submission here gets its own verdict, not combined with it");
    await user.click(screen.getByRole("button", { name: /^Submit/ }));
    expect(await screen.findByTestId("follows-up")).toHaveTextContent("A follow-up to Two Sum, a different problem. Its own verdict, not combined with that problem's or compared with it.");
    expect(sent[0]!.follows_up_submission_id).toBe("sub-1");
    // Only the first: the banner goes, and the next submission is an ordinary attempt.
    await expect.poll(() => screen.queryByRole("region", { name: "A follow-up problem" })).toBeNull();
  });

  it("a run from the offer doesn't carry the link", async () => {
    const sent: SubmissionCreate[] = [];
    server.use(...judgedOnSubmit(passed({ mode: "run" }), sent));
    const { user } = renderApp("/problems/two-sum-sorted?followUpOf=sub-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: /^Run/ }, { timeout: 4000 }));
    await expect.poll(() => sent.length).toBe(1);
    expect(sent[0]!.follows_up_submission_id).toBeUndefined();
    expect(screen.getByRole("region", { name: "A follow-up problem" })).toBeInTheDocument();
  });

  it("follow-ups submitted are listed beside the problem with their own verdicts", async () => {
    server.use(http.get(`${API}/api/v1/problems/two-sum/follow-ups`, () => HttpResponse.json(done)));
    renderApp("/problems/two-sum", { signedIn: true });
    const box = await screen.findByRole("region", { name: "Follow-ups you submitted" }, { timeout: 4000 });
    expect(box).toHaveTextContent("Each is a different problem with its own verdict, not combined with this problem's or compared with it.");
    expect(within(box).getByRole("link", { name: "Two Sum in a Sorted Array" })).toHaveAttribute("href", "/history/submissions/sub-9");
    expect(box).toHaveTextContent(/Failed\s*1 of 6 tests passed/);
  });

  it("at phone size the offer is in the Code tab, under the result", async () => {
    window.matchMedia = ((q: string) => ({ matches: q.includes("max-width: 900px"), media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false })) as typeof window.matchMedia;
    server.use(...judgedOnSubmit(passed()), http.get(`${API}/api/v1/problems/two-sum/follow-ups`, () => HttpResponse.json(offered)));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("tab", { name: "Code" }, { timeout: 4000 }));
    await user.click(await screen.findByRole("button", { name: /^Submit/ }));
    expect(await screen.findByRole("tab", { name: "Code", selected: true })).toBeInTheDocument();
    const results = await screen.findByRole("region", { name: "Submission results" });
    expect(await within(results).findByRole("region", { name: "A related problem" }, { timeout: 3000 })).toBeInTheDocument();
  });
});
