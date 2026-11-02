import { act, screen, waitFor, within } from "@testing-library/react";

import { renderApp } from "../render";

describe("Problem library", () => {
  it("updates the search field and results when the URL changes", async () => {
    const { router } = renderApp("/problems?q=zzz");
    expect(await screen.findByText("No problems match")).toBeInTheDocument();
    await act(async () => { await router.navigate("/problems?q=sum"); });
    expect(screen.getByRole("searchbox", { name: /search problems/i })).toHaveValue("sum");
    expect(await screen.findByText("Two Sum")).toBeInTheDocument();
    expect(screen.queryByText("No problems match")).not.toBeInTheDocument();
  });
  it("lists problems with difficulty and topics", async () => {
    renderApp("/problems");
    expect(await screen.findByText("Two Sum")).toBeInTheDocument();
    expect(screen.getByText("Maximum Subarray Sum")).toBeInTheDocument();
    expect(screen.getByText("3 problems")).toBeInTheDocument();
    const row = screen.getByText("Maximum Subarray Sum").closest("a") as HTMLElement;
    expect(within(row).getByText("Medium")).toBeInTheDocument();
    expect(row).toHaveAttribute("href", "/problems/maximum-subarray");
  });

  it("filters by topic chip and syncs the URL", async () => {
    const { user, router } = renderApp("/problems");
    await user.click(await screen.findByRole("button", { name: /hash maps/i }));
    await waitFor(() => expect(screen.queryByText("Maximum Subarray Sum")).not.toBeInTheDocument());
    expect(screen.getByText("Two Sum")).toBeInTheDocument();
    expect(router.state.location.search).toContain("topic=hash-maps");
    expect(screen.getByRole("button", { name: /hash maps/i })).toHaveAttribute("aria-pressed", "true");
  });

  it("debounces search and shows an empty state with a reset", async () => {
    const { user } = renderApp("/problems");
    await screen.findByText("Two Sum");
    await user.type(screen.getByRole("searchbox", { name: /search problems/i }), "zzz");
    expect(await screen.findByText("No problems match")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(await screen.findByText("Two Sum")).toBeInTheDocument();
  });

  it("shows per-problem status and recommendations when signed in", async () => {
    renderApp("/problems", { signedIn: true });
    const row = (await screen.findByText("Two Sum")).closest("a") as HTMLElement;
    expect(await within(row).findByLabelText("Solved")).toBeInTheDocument(); // once the session restores
    expect(await screen.findByText("Recommended for you")).toBeInTheDocument();
  });
});
