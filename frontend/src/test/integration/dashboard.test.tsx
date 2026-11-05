import { screen, within } from "@testing-library/react";

import { heatLevel } from "@/features/dashboard/heatLevel";

import { renderApp } from "../render";

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
