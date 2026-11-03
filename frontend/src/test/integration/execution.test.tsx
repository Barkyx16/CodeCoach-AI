import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Submission } from "@/api/types";

import { executionStatus, queuedSubmission } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const caps = (state: "ready" | "unavailable" | "not_configured", help: string | null = null) =>
  http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({ execution_enabled: state !== "not_configured", ai_provider: "offline", execution: executionStatus(state, help), guest_retention_days: 30 }));

describe("Code execution states", () => {
  it("a configured but unreachable judge pauses Run, keeps Submit (queued), and shows developer help", async () => {
    server.use(caps("unavailable", "The API can't reach RUNNER_URL. See docs/REMOTE_JUDGE.md."));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    const banner = await screen.findByText("The code judge is temporarily unavailable.");
    const box = banner.closest("[role=status]") as HTMLElement;
    expect(box).toHaveTextContent("Submissions wait in the queue and are judged when it's back; Run is paused.");
    expect(screen.queryByRole("button", { name: "Run" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Submit/ })).toBeEnabled();
    await user.click(within(box).getByText("Developer setup"));
    expect(within(box).getByText(/docs\/REMOTE_JUDGE\.md/)).toBeVisible();
  });

  it("a ready judge shows Run and Submit and no warning", async () => {
    server.use(caps("ready"));
    renderApp("/problems/two-sum", { signedIn: true });
    expect(await screen.findByRole("button", { name: "Run" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Submit/ })).toBeInTheDocument();
    expect(screen.queryByText(/temporarily unavailable|can't run on this server/)).not.toBeInTheDocument();
  });

  it("retries a submission whose response was lost with the same request id", async () => {
    server.use(caps("ready"));
    const ids: string[] = [];
    let attempt = 0;
    server.use(http.post(`${API}/api/v1/submissions`, async ({ request }) => {
      ids.push(((await request.json()) as { client_request_id: string }).client_request_id);
      attempt += 1;
      if (attempt === 1) return HttpResponse.error(); // connection dropped: did the server get it?
      return HttpResponse.json({ ...queuedSubmission, execution_enabled: true }, { status: 202 });
    }));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: /^Submit/ }));
    const alert = await screen.findByText(/We couldn't confirm your submission because the connection dropped/);
    await user.click(within(alert.closest("[role=alert]") as HTMLElement).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(ids).toHaveLength(2));
    expect(ids[0]).toBeTruthy();
    expect(ids[1]).toBe(ids[0]);
    await waitFor(() => expect(screen.queryByText(/We couldn't confirm/)).not.toBeInTheDocument());
  });

  it("after a reload, a submission that is still being judged is picked up again", async () => {
    server.use(caps("ready"));
    const running: Submission = { ...queuedSubmission, id: "sub-9", status: "RUNNING", execution_enabled: true, created_at: new Date().toISOString() };
    let polls = 0;
    server.use(
      http.get(`${API}/api/v1/me/submissions`, () => HttpResponse.json({ items: [{ id: "sub-9", problem_slug: "two-sum", problem_title: "Two Sum", mode: "submit", status: "RUNNING", created_at: running.created_at, duration_ms: null }], total: 1, page: 1, page_size: 1 })),
      http.get(`${API}/api/v1/submissions/sub-9`, () => {
        polls += 1;
        return HttpResponse.json(polls < 2 ? running : { ...running, status: "PASSED", is_terminal: true, status_detail: "All tests passed.",
          result: { runtime_ms: 4, memory_kb: null, passed_count: 3, total_count: 3, hidden_passed: 2, hidden_total: 2, stderr_excerpt: null, public_results: [] } });
      }),
    );
    renderApp("/problems/two-sum", { signedIn: true });
    expect(await screen.findByText("Running your code against the tests…")).toBeInTheDocument();
    expect(await screen.findByText("All tests passed. Nice work.", {}, { timeout: 4000 })).toBeInTheDocument();
  });
});
