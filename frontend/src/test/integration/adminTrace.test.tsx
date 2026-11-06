import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const TRACE = "4bf92f3577b34da6a3ce929d0e0e4736";
const span = (name: string, span_id: string, parent_id: string | null, outcome: string, attrs: Record<string, string | number> = {}, at = 0) => ({
  span_id, parent_id, name, started_at: 1_700_000_000 + at, duration_ms: 12.5, outcome, attrs, request_id: "req-00000001", source: "server",
});

it("an admin follows one action: the server's steps nested in order, and what the browser saw", async () => {
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, is_admin: true } }))),
    http.get(`${API}/api/v1/admin/traces/:id`, ({ params }) => params.id === "req-00000001" ? HttpResponse.json({
      trace_id: TRACE,
      spans: [
        span("db.commit", "c".repeat(16), "b".repeat(16), "ok", {}, 0.03),
        span("http", "a".repeat(16), "f".repeat(16), "ok", { route: "/api/v1/interviews/{interview_id}/answers", status: 200 }),
        span("round.action", "b".repeat(16), "a".repeat(16), "ok", { action: "answer", result: "advanced" }, 0.01),
      ],
      events: [{ source: "browser", action: "answer", outcome: "network_error", duration_ms: 812, request_id: "req-00000001", status: 0, error_code: null, at: 1_700_000_001 }],
    }) : HttpResponse.json({ error: { code: "trace_not_found", message: "No recent trace with that id on this server.", request_id: "r", details: null } }, { status: 404 })),
  );
  const { user } = renderApp("/admin/traces", { signedIn: true });
  await user.type(await screen.findByLabelText("Trace id or request id"), "req-00000001");
  await user.click(screen.getByRole("button", { name: "Look up" }));
  const serverSide = await screen.findByRole("region", { name: "On the server" });
  const rows = within(serverSide).getAllByRole("listitem").map((li) => li.textContent ?? "");
  expect(rows.map((r) => r.split(" ")[0])).toEqual(["http", "round.action", "db.commit"]); // parent before child
  expect(rows[1]).toContain("result=advanced");
  const browser = screen.getByRole("region", { name: "In the browser" });
  expect(browser).toHaveTextContent(/answer: network_error after 812 ms · HTTP 0/);
  expect(screen.getByText(TRACE)).toBeInTheDocument();

  await user.clear(screen.getByLabelText("Trace id or request id"));
  await user.type(screen.getByLabelText("Trace id or request id"), "unknown-trace-0000");
  await user.click(screen.getByRole("button", { name: "Look up" }));
  expect(await screen.findByText(/No recent trace with that id/)).toBeInTheDocument();
});
