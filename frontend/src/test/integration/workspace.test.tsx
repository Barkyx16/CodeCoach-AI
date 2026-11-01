import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { renderApp } from "../render";
import { API, server } from "../server";

describe("Problem workspace", () => {
  it("renders the statement, examples, public tests and starter code", async () => {
    renderApp("/problems/two-sum");
    expect(await screen.findByRole("heading", { name: "Two Sum", level: 1 })).toBeInTheDocument();
    expect(screen.getAllByText("nums = [2, 7, 11, 15], target = 9").length).toBeGreaterThan(0);
    expect(screen.getByText(/1 public · 4 hidden/)).toBeInTheDocument();
    const editor = await screen.findByLabelText(/java code editor/i);
    expect((editor as HTMLTextAreaElement).value).toContain("public int[] twoSum");
  });

  it("shows a friendly not-found state", async () => {
    renderApp("/problems/does-not-exist");
    expect(await screen.findByText("Problem 'does-not-exist' not found")).toBeInTheDocument();
    expect(screen.getByText("Reference:")).toBeInTheDocument();
  });

  it("autosaves the draft and restores it", async () => {
    const { user, unmount } = renderApp("/problems/two-sum", { signedIn: true });
    const editor = await screen.findByLabelText(/java code editor/i);
    // jsdom gives every element a 0x0 box, so the resizable-panel library treats any pointer
    // event as a drag on a separator. Focus the editor directly instead of clicking it.
    // (Real-browser typing is covered by the Playwright smoke test.)
    editor.focus();
    await user.clear(editor);
    editor.focus();
    await user.type(editor, "class Solution {{}", { skipClick: true });
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(await screen.findByText("Draft saved", {}, { timeout: 2000 })).toBeInTheDocument();
    unmount();
    renderApp("/problems/two-sum", { signedIn: true });
    expect(((await screen.findByLabelText(/java code editor/i)) as HTMLTextAreaElement).value).toBe("class Solution {}");
  });

  it("submits and explains that execution is disabled (no endless polling)", async () => {
    let posted: unknown = null;
    server.use(http.post(`${API}/api/v1/submissions`, async ({ request }) => {
      posted = await request.json();
      const { queuedSubmission } = await import("../fixtures");
      return HttpResponse.json(queuedSubmission, { status: 202 });
    }));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Submit" }));
    expect(await screen.findByText("Saved, but not run yet.")).toBeInTheDocument();
    expect(screen.getByText("Queued")).toBeInTheDocument();
    expect(posted).toMatchObject({ problem_slug: "two-sum", language: "java" });
  });

  it("sends signed-out users to login when they submit", async () => {
    const { user, router } = renderApp("/problems/two-sum");
    await user.click(await screen.findByRole("button", { name: "Submit" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });

  it("unlocks hints one level at a time", async () => {
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Get a hint" }));
    expect(await screen.findByText("Hint text for level 1")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Unlock level 2: Concept" }));
    expect(await screen.findByText("Hint text for level 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unlock level 3: Pseudocode" })).toBeInTheDocument();
    expect(screen.getByText("48/50 left")).toBeInTheDocument();
  });

  it("restores previously unlocked hints from history", async () => {
    server.use(http.get(`${API}/api/v1/me/ai-history`, () => HttpResponse.json({
      items: [{ id: "h1", problem_slug: "two-sum", problem_title: "Two Sum", action: "hint", hint_level: 1, provider: "offline",
        created_at: new Date().toISOString(), response: { hint: "Saved hint from yesterday", focus_area: "x", encouragement: "y" } }],
      total: 1, page: 1, page_size: 50,
    })));
    renderApp("/problems/two-sum", { signedIn: true });
    expect(await screen.findByText("Saved hint from yesterday")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unlock level 2: Concept" })).toBeInTheDocument();
  });

  it("shows a structured review with issues and complexity vs target", async () => {
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("tab", { name: "Code review" }));
    await user.click(screen.getByRole("button", { name: "Review my code" }));
    expect(await screen.findByText("Nested loops make this roughly O(n^2).")).toBeInTheDocument();
    expect(screen.getAllByText("target O(n)")).toHaveLength(2); // time and space targets
    expect(screen.getByRole("button", { name: "line 3" })).toBeInTheDocument();
    expect(screen.getByText(/never from the AI/)).toBeInTheDocument();
  });

  it("shows the budget error when the daily AI limit is hit", async () => {
    server.use(http.post(`${API}/api/v1/ai/hint`, () => HttpResponse.json({ error: { code: "rate_limited",
      message: "You've used today's AI coaching budget.", request_id: null, details: { daily_limit: 50 } } }, { status: 429 })));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Get a hint" }));
    expect(await screen.findByText("You've used today's AI coaching budget.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Get a hint" })).toBeDisabled();
  });

  it("asks signed-out users to sign in before using the coach", async () => {
    renderApp("/problems/two-sum");
    const coach = await screen.findByRole("region", { name: "AI coach" });
    expect(within(coach).getByRole("button", { name: /sign in or continue as guest/i })).toBeInTheDocument();
  });
});
