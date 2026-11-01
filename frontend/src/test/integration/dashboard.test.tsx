import { screen, within } from "@testing-library/react";

import { heatLevel } from "@/features/dashboard/heatLevel";

import { renderApp } from "../render";

describe("Dashboard", () => {
  it("shows stat tiles, recommendations and charts", async () => {
    renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByText("Ada's progress")).toBeInTheDocument();
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
  it("lists submissions and switches to AI feedback", async () => {
    const { user } = renderApp("/history", { signedIn: true });
    expect(await screen.findByRole("link", { name: "Two Sum" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "AI feedback" }));
    expect(await screen.findByText("No AI feedback yet")).toBeInTheDocument();
  });
});
