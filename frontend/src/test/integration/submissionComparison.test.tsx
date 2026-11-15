import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Submission, SubmissionComparison } from "@/api/types";

import { activityItems, executionStatus, queuedSubmission } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

/**
 * A coding submission beside the previous judged one (Volume 14, prompt 1;
 * docs/COMPARING_ATTEMPTS.md, "Coding submissions"): both verdicts as judged, the server's
 * explanation word for word, and nothing that says one improved on the other.
 */
const result = (passed: number, total = 7, hidden: readonly [number, number] = [0, 4]) => ({
  runtime_ms: 1, memory_kb: null, passed_count: passed, total_count: total, hidden_passed: hidden[0], hidden_total: hidden[1],
  stderr_excerpt: null, public_results: [],
});
const PARTLY = "Partly comparable: the in-app help differed: before the earlier one, hint shown; before the later one, none recorded. The counts are from the same tests, so both are shown. (Comparison rules v1)";
const compared = (explanation = PARTLY, outcome: SubmissionComparison["comparison"]["outcome"] = "partially_comparable"): SubmissionComparison => ({
  previous: { id: "sub-0", status: "FAILED", created_at: "2026-11-15T07:00:00Z", passed_count: 2, total_count: 7, hidden_passed: 0, hidden_total: 4 },
  comparison: { against: "sub-0", outcome, scores_comparable: outcome !== "incompatible", points_comparable: outcome !== "incompatible", reasons: [], explanation, contract_version: 1 },
});
const passed = (over: Partial<Submission> = {}): Submission => ({
  ...queuedSubmission, status: "PASSED", status_detail: "All tests passed.", is_terminal: true, execution_enabled: true,
  result: result(7, 7, [4, 4]), compared: compared(), ...over,
});

describe("A coding submission beside the one before it", () => {
  it("the submission's page shows both verdicts, their counts and the explanation", async () => {
    server.use(http.get(`${API}/api/v1/submissions/:id`, () => HttpResponse.json(passed())));
    renderApp("/history/submissions/sub-1", { signedIn: true });
    const box = await screen.findByRole("region", { name: "Compared with your previous submission" });
    const [earlier, now] = within(box).getAllByRole("listitem");
    expect(earlier).toHaveTextContent(/Earlier, .*: Failed 2 of 7 tests passed \(hidden 0 of 4\)/);
    expect(now).toHaveTextContent("This one: Passed 7 of 7 tests passed (hidden 4 of 4)");
    expect(within(box).getByText(PARTLY)).toBeInTheDocument();
    expect(box.textContent).not.toMatch(/improv|better|average/i);
  });

  it("with no earlier judged submission, nothing is compared", async () => {
    server.use(http.get(`${API}/api/v1/submissions/:id`, () => HttpResponse.json(passed({ compared: null }))));
    renderApp("/history/submissions/sub-1", { signedIn: true });
    await screen.findByRole("heading", { name: "Result" });
    expect(screen.queryByRole("region", { name: /Compared with your previous/ })).not.toBeInTheDocument();
  });

  it("the workspace's result says it under the counts once the verdict is in", async () => {
    const judged = passed({
      compared: compared("Not comparable: this one wasn't judged, so there's no verdict to set beside the other. (Comparison rules v1)", "incompatible"),
    });
    server.use(
      http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({ execution_enabled: true, ai_provider: "offline", execution: executionStatus("ready", null), guest_retention_days: 30 })),
      http.post(`${API}/api/v1/submissions`, () => HttpResponse.json(judged, { status: 202 })),
      http.get(`${API}/api/v1/submissions/sub-1`, () => HttpResponse.json(judged)),
    );
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: /^Submit/ }, { timeout: 4000 }));
    const box = await screen.findByRole("region", { name: "Compared with your previous submission" });
    expect(within(box).getByText(/^Not comparable: this one wasn't judged/)).toBeInTheDocument();
  });

  it("History gives each submission row the outcome the server gave it", async () => {
    const rows = activityItems.map((i) => (i.type === "code_submission" ? { ...i, detail: "Partly comparable with the one before" } : i));
    server.use(http.get(`${API}/api/v1/me/activity`, () => HttpResponse.json({ items: rows, total: rows.length, page: 1, page_size: 20 })));
    renderApp("/history", { signedIn: true });
    expect(await screen.findByText(/Partly comparable with the one before/)).toBeInTheDocument();
  });
});
