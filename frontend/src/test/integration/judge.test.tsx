import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Submission } from "@/api/types";

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
            exception: "ArrayIndexOutOfBoundsException", exception_message: "Index 2 out of bounds for length 2", missing: false, runtime_ms: 0.1 },
          { index: 1, passed: false, input: { nums: [3, 2, 4], target: 6 }, expected_output: [1, 2], actual_output: null,
            exception: null, exception_message: null, missing: true, runtime_ms: null },
        ] },
    });
    serveSequence([crashed]);
    await submitTwoSum();
    expect(await screen.findByText("ArrayIndexOutOfBoundsException")).toBeInTheDocument();
    expect(screen.getByText(/Index 2 out of bounds for length 2/)).toBeInTheDocument();
    expect(screen.getByText(/this test never ran/)).toBeInTheDocument();
  });
});
