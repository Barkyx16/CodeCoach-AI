import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { heatLevel } from "@/features/dashboard/heatLevel";

import { renderApp } from "../render";
import { API, server } from "../server";

describe("Dashboard", () => {
  it("shows stat tiles, recommendations and charts", async () => {
    renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Your interview practice" })).toBeInTheDocument();
    const summary = screen.getByRole("region", { name: "Summary" });
    expect(within(summary).getByText("Solved").nextElementSibling).toHaveTextContent("1");
    expect(screen.getByText("3 days")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(await screen.findByText(/without a pass/)).toBeInTheDocument();
    expect(screen.getAllByTestId("heat-cell")).toHaveLength(28);
    expect(screen.getByRole("img", { name: /Arrays: 1\/6 solved, 1 in progress/ })).toBeInTheDocument();
  });

  it("says how each recent attempt compares with the one before, linking to that comparison", async () => {
    const at = new Date().toISOString();
    const row = (id: string, status: string, outcome_text: string | null) =>
      ({ id, problem_slug: "two-sum", problem_title: "Two Sum", mode: "submit", status, created_at: at, duration_ms: 3, outcome_text });
    server.use(http.get(`${API}/api/v1/me/submissions`, () => HttpResponse.json({
      items: [row("s-2", "PASSED", "Comparable with the one before"), row("s-1", "FAILED", "Not compared: the first judged submission of this problem")],
      total: 2, page: 1, page_size: 4,
    })));
    renderApp("/dashboard", { signedIn: true });
    const card = (await screen.findByRole("heading", { name: "Recent attempts" })).closest(".recent-activity") as HTMLElement;
    expect(await within(card).findByRole("link", { name: "Comparable with the one before" })).toHaveAttribute("href", "/history/submissions/s-2#comparison");
    expect(card).toHaveTextContent("Not compared: the first judged submission of this problem");
    expect(within(card).queryByRole("link", { name: /Not compared/ })).not.toBeInTheDocument();
  });

  it("offers a table view of the heatmap", async () => {
    const { user } = renderApp("/dashboard", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Show table" }));
    expect(screen.getAllByRole("row")).toHaveLength(29); // header + 28 days
  });

  it("buckets activity into sequential levels", () => {
    expect([0, 1, 2, 3, 5, 6, 9, 10, 50].map(heatLevel)).toEqual([0, 1, 1, 2, 2, 3, 3, 4, 4]);
  });
});

describe("History", () => {
  it("old tab links still open the matching History filter", async () => {
    const { router } = renderApp("/history?tab=interviews", { signedIn: true });
    expect(await screen.findByText("Registered Nurse question round")).toBeInTheDocument();
    expect(router.state.location.search).toBe("?type=interview");
  });
});
