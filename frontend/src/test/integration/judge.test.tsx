import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ExplainFailureResponse, Submission } from "@/api/types";

import { queuedSubmission } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const judged = (overrides: Partial<Submission>): Submission => ({
  ...queuedSubmission, execution_enabled: true, is_terminal: true, ...overrides,
});

function serveSequence(states: Submission[]) {
  let calls = 0;
  server.use(
    http.post(`${API}/api/v1/submissions`, () => HttpResponse.json(states[0], { status: 202 })),
    // Each GET returns the next state in order: the job is seen QUEUED, then RUNNING, then judged.
    http.get(`${API}/api/v1/submissions/:id`, () => {
      const state = states[Math.min(calls, states.length - 1)];
      calls += 1;
      return HttpResponse.json(state);
    }),
  );
  return () => calls;
}

async function submitTwoSum() {
  const ctx = renderApp("/problems/two-sum", { signedIn: true });
  await ctx.user.click(await ctx.findByRole("button", { name: "Submit" }));
  return ctx;
}

describe("Judge results", () => {
  it("polls a queued job until it is judged", async () => {
    const queued = { ...queuedSubmission, execution_enabled: true, status_detail: "Waiting for a judge…" };
    const running = { ...queued, status: "RUNNING" as const };
    const passed = judged({
      status: "PASSED", status_detail: "All tests passed.",
      result: { runtime_ms: 3, memory_kb: null, passed_count: 7, total_count: 7, hidden_passed: 4, hidden_total: 4,
        stderr_excerpt: null,
        public_results: [{ index: 0, passed: true, input: { nums: [2, 7, 11, 15], target: 9 }, expected_output: [0, 1],
          actual_output: [0, 1], exception: null, exception_message: null, missing: false, runtime_ms: 0.4 }] },
    });
    const calls = serveSequence([queued, running, passed]);
    await submitTwoSum();
    expect(await screen.findByText("Waiting for a judge…")).toBeInTheDocument();
    expect(await screen.findByText("All tests passed. Nice work.", {}, { timeout: 6000 })).toBeInTheDocument();
    expect(screen.getByText("hidden: 4/4")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    const after = calls();
    await new Promise((r) => setTimeout(r, 1700));
    expect(calls()).toBe(after); // polling stopped once the verdict was final
  }, 15_000);

  it("shows compiler output for compile errors", async () => {
    const compile = judged({
      status: "COMPILE_ERROR", status_detail: "Your code didn't compile.",
      result: { runtime_ms: null, memory_kb: null, passed_count: 0, total_count: 7, hidden_passed: 0, hidden_total: 4,
        public_results: [], stderr_excerpt: "Solution.java:3: error: ';' expected" },
    });
    serveSequence([compile]);
    await submitTwoSum();
    expect(await screen.findByText("Compiler output")).toBeInTheDocument();
    expect(screen.getByText("Solution.java:3: error: ';' expected")).toBeInTheDocument();
  });

  it("explains exceptions and tests that never ran", async () => {
    const crashed = judged({
      status: "RUNTIME_ERROR", status_detail: "Your code crashed or exited before finishing all tests.",
      result: { runtime_ms: 1, memory_kb: null, passed_count: 1, total_count: 7, hidden_passed: 0, hidden_total: 4,
        stderr_excerpt: null,
        public_results: [
          { index: 0, passed: false, input: { nums: [2, 7], target: 9 }, expected_output: [0, 1], actual_output: null,
            exception: "ArrayIndexOutOfBoundsException", exception_message: "Index 2 out of bounds for length 2", missing: false,
            line: 5, runtime_ms: 0.1 },
          { index: 1, passed: false, input: { nums: [3, 2, 4], target: 6 }, expected_output: [1, 2], actual_output: null,
            exception: null, exception_message: null, missing: true, runtime_ms: null },
        ] },
    });
    serveSequence([crashed]);
    await submitTwoSum();
    expect(await screen.findByText("ArrayIndexOutOfBoundsException")).toBeInTheDocument();
    expect(screen.getByText(/Index 2 out of bounds for length 2/)).toBeInTheDocument();
    expect(screen.getByText(/this test never ran/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "line 5" })).toBeInTheDocument(); // jumps to the crashing line
  });

  const explanation: ExplainFailureResponse = {
    submission_id: "sub-1", status: "FAILED", provider: "offline", cached: false,
    disclaimer: "Explanations are based only on the public tests and compiler output.",
    explanation: {
      cause: "index-out-of-bounds", headline: "An index went out of range at line 5.",
      explanation: "Valid indexes are 0 to length - 1, so check `i + 1` on the last element.",
      evidence: "Public test 1 (nums = [2, 7], target = 9) threw ArrayIndexOutOfBoundsException at line 5",
      line_hint: 5, next_steps: ["Check each loop bound.", "Handle empty input first."],
      concept: "Array bounds and off-by-one errors", confidence: "high",
    },
  };
  const failed = judged({
    status: "FAILED", status_detail: "Some tests failed.",
    result: { runtime_ms: 1, memory_kb: null, passed_count: 0, total_count: 7, hidden_passed: 0, hidden_total: 4,
      stderr_excerpt: null,
      public_results: [{ index: 0, passed: false, input: { nums: [2, 7], target: 9 }, expected_output: [0, 1],
        actual_output: null, exception: "ArrayIndexOutOfBoundsException", exception_message: "Index 2 out of bounds for length 2",
        missing: false, line: 5, runtime_ms: 0.1 }] },
  });

  it("explains a failed submission on request", async () => {
    let body: unknown = null;
    server.use(http.post(`${API}/api/v1/ai/explain-failure`, async ({ request }) => {
      body = await request.json();
      return HttpResponse.json(explanation);
    }));
    serveSequence([failed]);
    const ctx = await submitTwoSum();
    await ctx.user.click(await screen.findByRole("button", { name: "Explain this failure" }));
    expect(await screen.findByText("An index went out of range at line 5.")).toBeInTheDocument();
    expect(body).toEqual({ submission_id: failed.id });
    const why = screen.getByRole("region", { name: "Why it failed" });
    expect(why).toHaveTextContent("Index out of bounds");
    expect(why.querySelector("code")?.textContent).toBe("i + 1"); // backticks render as code, never as HTML
    expect(screen.getByRole("button", { name: "Go to line 5" })).toBeInTheDocument();
    expect(screen.getByText("Check each loop bound.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Explain this failure" })).not.toBeInTheDocument();
  });

  it("shows budget errors from the explainer", async () => {
    server.use(http.post(`${API}/api/v1/ai/explain-failure`, () => HttpResponse.json(
      { error: { code: "rate_limited", message: "You've used today's AI coaching budget.", request_id: "r", details: null } },
      { status: 429 })));
    serveSequence([failed]);
    const ctx = await submitTwoSum();
    await ctx.user.click(await screen.findByRole("button", { name: "Explain this failure" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/budget/i);
  });

  it("offers no explanation for passing or still-running submissions", async () => {
    serveSequence([judged({ status: "PASSED", status_detail: "All tests passed.", result: null })]);
    await submitTwoSum();
    expect(await screen.findByText("All tests passed. Nice work.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Explain this failure" })).not.toBeInTheDocument();
  });

  describe("Run (public tests only)", () => {
    const enableExecution = () => server.use(
      http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({ execution_enabled: true, ai_provider: "offline" })));

    it("is hidden when this deployment can't run code", async () => {
      renderApp("/problems/two-sum", { signedIn: true });
      expect(await screen.findByRole("button", { name: "Submit" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Run" })).not.toBeInTheDocument();
    });

    it("runs the public tests and says the attempt isn't recorded", async () => {
      enableExecution();
      let body: { mode?: string } = {};
      const ranOk = judged({
        mode: "run", status: "PASSED", status_detail: "All tests passed.",
        result: { runtime_ms: 1, memory_kb: null, passed_count: 3, total_count: 3, hidden_passed: 0, hidden_total: 0,
          stderr_excerpt: null, public_results: [] },
      });
      server.use(
        http.post(`${API}/api/v1/submissions`, async ({ request }) => {
          body = (await request.json()) as { mode?: string };
          return HttpResponse.json({ ...ranOk, status: "QUEUED", is_terminal: false }, { status: 202 });
        }),
        http.get(`${API}/api/v1/submissions/:id`, () => HttpResponse.json(ranOk)),
      );
      const ctx = renderApp("/problems/two-sum", { signedIn: true });
      await ctx.user.click(await screen.findByRole("button", { name: "Run" }));
      expect(body.mode).toBe("run");
      expect(await screen.findByText("Run · public tests only")).toBeInTheDocument();
      expect(screen.getByText("All public tests passed. Submit to check the hidden tests and record the attempt.")).toBeInTheDocument();
      expect(screen.queryByText(/^hidden:/)).not.toBeInTheDocument();
    });
  });
});

