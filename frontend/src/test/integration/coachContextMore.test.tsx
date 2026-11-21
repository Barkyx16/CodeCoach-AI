import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ExplainFailureResponse, Submission } from "@/api/types";

import { executionStatus, explainPreview, hint, hintPreview, queuedSubmission } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

/** What the coach reads for hints and failure explanations (Volume 13, prompt 2; docs/COACH_CONTEXT.md). */

async function openHints() {
  const ctx = renderApp("/problems/two-sum", { signedIn: true });
  await ctx.user.click(await screen.findByRole("button", { name: "Get a hint" }, { timeout: 5000 }));
  return ctx;
}

describe("A hint: check, then send", () => {
  it("shows what the coach will read for the level, sends exactly that, and Cancel sends nothing", async () => {
    const sent: unknown[] = [];
    server.use(http.post(`${API}/api/v1/ai/hint`, async ({ request }) => {
      sent.push(await request.json());
      return HttpResponse.json(hint(1));
    }));
    const { user } = await openHints();
    const context = await screen.findByRole("region", { name: "What the coach will read" });
    expect(context).toHaveTextContent("Level 1 of 4: Nudge.");
    expect(context).toHaveTextContent("Your first hint for this problem.");
    expect(context).toHaveTextContent("Which levels you've seen isn't sent; the level you ask for is.");
    expect(within(context).getByLabelText("Exactly what's sent: The hint level you're asking for")).toHaveTextContent("Requested hint level: 1 (nudge).");
    expect(context).toHaveTextContent("It isn't shown here, so checking doesn't give the hint away.");
    expect(within(context).queryByRole("checkbox")).not.toBeInTheDocument(); // nothing optional for a hint

    await user.click(within(context).getByRole("button", { name: "Cancel" }));
    expect(await screen.findByText("Cancelled. Nothing was sent.")).toBeInTheDocument();
    expect(sent).toEqual([]);

    await user.click(screen.getByRole("button", { name: "Get a hint" }));
    await user.click(await screen.findByRole("button", { name: "Ask for the level 1 hint" }));
    expect(await screen.findByText("Hint text for level 1")).toBeInTheDocument();
    expect(sent).toHaveLength(1);
    expect(sent[0]).toMatchObject({ problem_slug: "two-sum", level: 1, approved_context: "v1:hint-1" });
  });

  it("refused because what it would read changed: says nothing was sent and shows the new material", async () => {
    let calls = 0;
    server.use(http.post(`${API}/api/v1/ai/hint`, () => {
      calls += 1;
      return HttpResponse.json({ error: { code: "context_changed", message: "changed", request_id: "r",
        details: { preview: hintPreview(1, { code: "class Solution { /* now */ }", fingerprint: "v1:hint-1-now" }) } } }, { status: 409 });
    }));
    const { user } = await openHints();
    await user.click(await screen.findByRole("button", { name: "Ask for the level 1 hint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("What the coach would read changed since you checked it, so nothing was sent.");
    expect(screen.getByLabelText("Exactly what's sent: Your code")).toHaveTextContent("/* now */");
    expect(screen.queryByText("Hint text for level 1")).not.toBeInTheDocument();
    expect(calls).toBe(1);
  });
});

const judged = (overrides: Partial<Submission>): Submission => ({ ...queuedSubmission, execution_enabled: true, is_terminal: true, ...overrides });
const failed = (id: string) => judged({
  id, status: "FAILED", status_detail: "Some tests failed.",
  result: { runtime_ms: 1, memory_kb: null, passed_count: 1, total_count: 7, hidden_passed: 0, hidden_total: 5, stderr_excerpt: null,
    public_results: [{ index: 1, passed: false, input: { nums: [3, 2, 4], target: 6 }, expected_output: [1, 2], actual_output: [0, 0],
      exception: null, exception_message: null, missing: false, line: null, runtime_ms: 0.1 }] },
});
const explanation: ExplainFailureResponse = {
  submission_id: "sub-a", status: "FAILED", provider: "offline", cached: false, disclaimer: "Advisory; the judge decides correctness.",
  explanation: { cause: "wrong-answer", headline: "The pair search returns the wrong indices.", explanation: "x", evidence: "Public test 2",
    line_hint: null, next_steps: ["Trace the loop."], concept: null, confidence: "medium" },
};

async function failedOnce(id = "sub-a") {
  server.use(
    http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({ execution_enabled: true, ai_provider: "offline", execution: executionStatus("ready"), guest_retention_days: 30 })),
    http.post(`${API}/api/v1/submissions`, () => HttpResponse.json(failed(id), { status: 202 })),
    http.get(`${API}/api/v1/submissions/:id`, ({ params }) => HttpResponse.json(failed(String(params.id)))),
  );
  const ctx = renderApp("/problems/two-sum", { signedIn: true });
  await ctx.user.click(await ctx.findByRole("button", { name: "Submit" }, { timeout: 5000 }));
  await ctx.user.click(await screen.findByRole("button", { name: "Explain this failure" }));
  return ctx;
}

describe("Explaining a failure: check, then send", () => {
  it("lists what's sent, lets the optional items be left out, and sends that choice bound to the preview", async () => {
    const previews: unknown[] = [];
    const sent: unknown[] = [];
    server.use(
      http.post(`${API}/api/v1/ai/explain-failure/preview`, async ({ request }) => {
        const body = (await request.json()) as { share_compile_output: boolean; share_failing_test: boolean };
        previews.push(body);
        return HttpResponse.json(explainPreview({ compile: body.share_compile_output, failing: body.share_failing_test }));
      }),
      http.post(`${API}/api/v1/ai/explain-failure`, async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json(explanation);
      }),
    );
    const { user } = await failedOnce();
    const context = await screen.findByRole("region", { name: "What the coach will read" });
    expect(context).toHaveTextContent("Explains your submission of 14 November 2026, 10:42 UTC (failed tests).");
    expect(context).toHaveTextContent("One explanation is kept for each submission: asking again shows it and sends nothing.");
    expect(within(context).getByLabelText("Exactly what's sent: How many tests passed")).toHaveTextContent("hidden inputs are secret");
    await user.click(within(context).getByRole("checkbox", { name: "Send the failing public test" }));
    await waitFor(() => expect(previews).toContainEqual({ submission_id: "sub-a", share_compile_output: true, share_failing_test: false }));
    expect(await within(context).findByText("You left it out.")).toBeInTheDocument();
    expect(within(context).queryByLabelText("Exactly what's sent: The first failing public test, with your program's output")).not.toBeInTheDocument();
    await user.click(within(context).getByRole("button", { name: "Ask for the explanation" }));
    expect(await screen.findByText("The pair search returns the wrong indices.")).toBeInTheDocument();
    expect(sent).toEqual([{ submission_id: "sub-a", share_compile_output: true, share_failing_test: false, approved_context: "v1:explain-10" }]);
  });

  it("an explanation already kept: says so, and the button shows it rather than sending", async () => {
    server.use(http.post(`${API}/api/v1/ai/explain-failure/preview`, () => HttpResponse.json(explainPreview({ answered: true }))));
    await failedOnce();
    const context = await screen.findByRole("region", { name: "What the coach will read" });
    expect(context).toHaveTextContent("This submission was explained before: asking again shows that explanation and sends nothing.");
    expect(context).toHaveTextContent("so is showing what was kept: nothing is sent.");
    expect(within(context).getByRole("button", { name: "Show the explanation" })).toBeEnabled();
  });

  it("refused because what it would read changed: nothing was sent, and the new material is shown", async () => {
    let calls = 0;
    server.use(http.post(`${API}/api/v1/ai/explain-failure`, () => {
      calls += 1;
      return HttpResponse.json({ error: { code: "context_changed", message: "changed", request_id: "r",
        details: { preview: explainPreview({ fingerprint: "v1:explain-now" }) } } }, { status: 409 });
    }));
    const { user } = await failedOnce();
    await user.click(await screen.findByRole("button", { name: "Ask for the explanation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("What the coach would read changed since you checked it, so nothing was sent.");
    expect(screen.queryByRole("region", { name: "Why it failed" })).not.toBeInTheDocument();
    expect(calls).toBe(1);
  });
});
