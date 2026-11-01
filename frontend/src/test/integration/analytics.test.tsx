import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { renderApp } from "../render";
import { API, server } from "../server";

describe("Analytics", () => {
  it("uses backend metrics and identifies the activity window honestly", async () => {
    const { user } = renderApp("/analytics", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Analytics" })).toBeInTheDocument();
    const summary = within(screen.getByRole("region", { name: "Practice statistics" }));
    expect(summary.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText(/includes problem opens, submissions, coaching and completed interviews/)).toBeInTheDocument();
    expect(screen.getAllByTestId("heat-cell")).toHaveLength(28);
    await user.click(screen.getByRole("button", { name: "Show table" }));
    expect(screen.getAllByRole("row")).toHaveLength(29);
    expect(await screen.findByText("A new perspective on your skills")).toBeInTheDocument();
  });

  it("offers a retry after a progress API failure", async () => {
    server.use(http.get(`${API}/api/v1/me/progress`, () => HttpResponse.json({
      error: { code: "unavailable", message: "Practice insights are temporarily unavailable." },
    }, { status: 503 })));
    renderApp("/analytics", { signedIn: true });
    expect(await screen.findByRole("alert")).toHaveTextContent("Practice insights are temporarily unavailable.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("requires authentication", async () => {
    const { router } = renderApp("/analytics");
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
  });
});
