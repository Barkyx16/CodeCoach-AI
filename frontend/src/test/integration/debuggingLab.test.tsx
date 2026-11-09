/**
 * The debugging lab (Volume 10, prompt 2; docs/DEBUGGING_LAB.md) on the coding workspace: the
 * brief says what the code should do and which public case shows the defect; the explanation and
 * repair wait until asked (or a passing fix); optional notes stay in this browser for this account;
 * the debrief is the judge's verdict in the lab's terms, never a pass the tests didn't give; and
 * History keeps the code an attempt started from apart from the code sent.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { LabExplanation, ProblemDetail, Submission } from "@/api/types";
import { debugNotesKey } from "@/features/debugging/notesKey";

import { executionStatus, page, queuedSubmission, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const starter = [
  "class Solution {",
  "    public int countAtMost(int[] nums, int limit) {",
  "        int count = 0;",
  "        for (int i = 0; i < nums.length - 1; i++) {",
  "            if (nums[i] <= limit) {",
  "                count++;",
  "            }",
  "        }",
  "        return count;",
  "    }",
  "}",
  "",
].join("\n");
const repaired = starter.replace("i < nums.length - 1;", "i < nums.length;");

const exercise: ProblemDetail = {
  slug: "debug-count-at-most", title: "Fix: Count Within a Limit", difficulty: "easy",
  topics: ["debugging", "arrays", "off-by-one"], summary: "A count that is sometimes one short.",
  statement: "`countAtMost(nums, limit)` should count the values at or below `limit`.",
  constraints: [], examples: [], starter_code: starter,
  signature: { method: "countAtMost", params: [{ name: "nums", type: "int[]" }, { name: "limit", type: "int" }], returns: "int" },
  public_tests: [
    { id: 11, input: { nums: [1, 5, 9], limit: 4 }, expected_output: 1 },
    { id: 12, input: { nums: [2, 3, 10], limit: 5 }, expected_output: 2 },
    { id: 13, input: { nums: [4, 8, 3], limit: 5 }, expected_output: 2 },
  ],
  hidden_test_count: 5, hint_levels: 3, kind: "debug",
  lab: { version: 1, intended_behavior: "Count every value at or below the limit, including the last one.", reproduction_test_ids: [13], review_status: "Authored and machine-checked." },
};
const explanation: LabExplanation = {
  version: 1, defect_summary: "The loop stops one index early.",
  explanation: "With nums.length - 1 the last value is never looked at.",
  why_missed: "If the last value is above the limit, skipping it changes nothing.",
  reference_repair: repaired, follow_up: "Write out the indexes a loop visits.",
};

let explanationCalls = 0;
function serveLab() {
  explanationCalls = 0;
  server.use(
    http.get(`${API}/api/v1/problems/debug-count-at-most`, () => HttpResponse.json(exercise)),
    http.get(`${API}/api/v1/problems/debug-count-at-most/lab/explanation`, () => { explanationCalls += 1; return HttpResponse.json(explanation); }),
    http.get(`${API}/api/v1/problems`, ({ request }) =>
      new URL(request.url).searchParams.get("kind") === "debug"
        ? HttpResponse.json(page([{ slug: exercise.slug, title: exercise.title, difficulty: exercise.difficulty, topics: exercise.topics, summary: exercise.summary }]))
        : HttpResponse.json(page([]))),
  );
}
const withJudge = () => server.use(http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({
  execution_enabled: true, ai_provider: "offline", execution: executionStatus("ready"), guest_retention_days: 30,
})));
const attempt = (overrides: Partial<Submission>): Submission => ({
  ...queuedSubmission, problem_slug: exercise.slug, problem_title: exercise.title, execution_enabled: true, is_terminal: true,
  starting_code: starter, lab_version: 1, source_code: repaired, ...overrides,
});
const serveAttempt = (s: Submission) => server.use(
  http.post(`${API}/api/v1/submissions`, () => HttpResponse.json(s, { status: 202 })),
  http.get(`${API}/api/v1/submissions/:id`, () => HttpResponse.json(s)),
);
const result = (passedCount: number, reproPassed: boolean, actual: number) => ({
  runtime_ms: 3, memory_kb: null, passed_count: passedCount, total_count: 8, hidden_passed: passedCount - 2, hidden_total: 5, stderr_excerpt: null,
  public_results: [
    { index: 0, passed: true, input: { nums: [1, 5, 9], limit: 4 }, expected_output: 1, actual_output: 1, exception: null, exception_message: null, missing: false },
    { index: 2, passed: reproPassed, input: { nums: [4, 8, 3], limit: 5 }, expected_output: 2, actual_output: actual, exception: null, exception_message: null, missing: false },
  ],
});

describe("the debugging lab", () => {
  it("is reached from the coding library and lists its exercises", async () => {
    serveLab();
    const { user } = renderApp("/problems", { signedIn: true });
    await user.click(await screen.findByRole("link", { name: "Debugging lab: fix programs with a known bug" }));
    expect(await screen.findByRole("heading", { name: "Fix a broken program", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Fix: Count Within a Limit" })).toHaveAttribute("href", "/problems/debug-count-at-most");
  });

  it("the brief names what the code should do and the case that shows the defect; the explanation waits until asked", async () => {
    serveLab();
    const { user } = renderApp("/problems/debug-count-at-most", { signedIn: true });
    const brief = await screen.findByRole("region", { name: "Fix the bug" });
    expect(brief).toHaveTextContent("Count every value at or below the limit, including the last one.");
    expect(within(brief).getByRole("listitem")).toHaveTextContent("nums = [4, 8, 3], limit = 5 should give 2");
    expect(brief).not.toHaveTextContent("one index early");
    await user.click(within(brief).getByRole("button", { name: "Stuck? Show the explanation" }));
    await user.click(within(brief).getByRole("button", { name: "Not yet" }));
    expect(explanationCalls).toBe(0); // asking and stepping back fetches nothing
    await user.click(within(brief).getByRole("button", { name: "Stuck? Show the explanation" }));
    await user.click(within(brief).getByRole("button", { name: "Show the explanation" }));
    expect(await within(brief).findByText("The loop stops one index early.")).toBeInTheDocument();
    expect(brief).toHaveTextContent("If the last value is above the limit, skipping it changes nothing.");
    expect(brief).toHaveTextContent("Yours doesn't have to look like this: the tests decide.");
    expect(explanationCalls).toBe(1);
  });

  it("investigation notes are optional, kept in this browser for this account, and come back", async () => {
    serveLab();
    const first = renderApp("/problems/debug-count-at-most", { signedIn: true });
    const brief = await screen.findByRole("region", { name: "Fix the bug" });
    await first.user.click(within(brief).getByText("Your investigation (optional)"));
    // Focus, then type: in jsdom (no layout) a pointer press anywhere lands on the panels' resize handle.
    within(brief).getByLabelText("Your hypothesis").focus();
    await first.user.keyboard("The loop skips the last value.");
    expect(JSON.parse(localStorage.getItem(debugNotesKey(baseUser.id, exercise.slug)) ?? "{}")).toEqual({ hypothesis: "The loop skips the last value." });
    first.unmount();
    serveLab();
    renderApp("/problems/debug-count-at-most", { signedIn: true });
    const again = await screen.findByRole("region", { name: "Fix the bug" });
    expect(within(again).getByLabelText("Your hypothesis")).toHaveValue("The loop skips the last value.");
  });

  it("a failing attempt: the case that showed the defect still fails, with what changed; no explanation is offered as a pass", async () => {
    serveLab();
    withJudge();
    serveAttempt(attempt({ status: "FAILED", status_detail: "6 of 8 tests passed.", source_code: starter.replace("int count = 0;", "int count = 0; // checked"), result: result(6, false, 1) }));
    const { user } = renderApp("/problems/debug-count-at-most", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Submit" }));
    const debrief = await screen.findByRole("region", { name: "Debugging debrief" });
    expect(within(debrief).getByRole("heading", { name: "Not fixed yet: 6 of 8 tests pass" })).toBeInTheDocument();
    expect(within(debrief).getByRole("list", { name: "The cases that showed the defect" })).toHaveTextContent("nums = [4, 8, 3], limit = 5: still fails (got 1, expected 2)");
    expect(debrief).toHaveTextContent("+ int count = 0; // checked");
    expect(debrief).toHaveTextContent("- int count = 0;");
    expect(debrief).not.toHaveTextContent("Why it happened");
    expect(explanationCalls).toBe(0);
  });

  it("a passing attempt: fixed, the case now passes, and why it happened is shown", async () => {
    serveLab();
    withJudge();
    serveAttempt(attempt({ status: "PASSED", status_detail: "All tests passed.", result: result(8, true, 2) }));
    const { user } = renderApp("/problems/debug-count-at-most", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Submit" }));
    const debrief = await screen.findByRole("region", { name: "Debugging debrief" });
    expect(within(debrief).getByRole("heading", { name: "Fixed: every test passes" })).toBeInTheDocument();
    expect(debrief).toHaveTextContent("nums = [4, 8, 3], limit = 5: now passes");
    expect(debrief).toHaveTextContent("- for (int i = 0; i < nums.length - 1; i++) {");
    expect(debrief).toHaveTextContent("+ for (int i = 0; i < nums.length; i++) {");
    expect(await within(debrief).findByRole("heading", { name: "Why it happened" })).toBeInTheDocument();
  });

  it("with no judge on this server, an attempt is saved and the debrief says it couldn't be checked", async () => {
    serveLab();
    serveAttempt(attempt({ status: "QUEUED", is_terminal: false, execution_enabled: false, result: null }));
    const { user } = renderApp("/problems/debug-count-at-most", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: /^Save attempt/ }));
    const debrief = await screen.findByRole("region", { name: "Debugging debrief" });
    expect(within(debrief).getByRole("heading", { name: "Saved, not checked" })).toBeInTheDocument();
    expect(debrief).toHaveTextContent("whether this fixes the defect can't be checked");
    expect(debrief).not.toHaveTextContent("Fixed");
  });

  it("History keeps the code an attempt started from apart from the code sent, with its version", async () => {
    server.use(http.get(`${API}/api/v1/submissions/:id`, () => HttpResponse.json(attempt({ status: "FAILED", result: result(6, false, 1), lab_version: 1 }))));
    renderApp("/history/submissions/sub-1", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Started from" })).toBeInTheDocument();
    expect(screen.getByText(/faulty code \(version 1\), as it was when you made this attempt/)).toBeInTheDocument();
    expect(screen.getByLabelText("Starting code")).toHaveTextContent("i < nums.length - 1;");
    expect(screen.getByLabelText("Submitted code")).toHaveTextContent("i < nums.length;");
    await waitFor(() => expect(screen.getByRole("heading", { name: "Submitted code" })).toBeInTheDocument());
  });
});
