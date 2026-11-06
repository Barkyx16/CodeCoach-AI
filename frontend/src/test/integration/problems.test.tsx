import { act, screen, waitFor, within } from "@testing-library/react";

import { http, HttpResponse } from "msw";

import { renderApp } from "../render";
import { API, server } from "../server";

describe("Problem library", () => {
  it("updates the search field and results when the URL changes", async () => {
    const { router } = renderApp("/problems?q=zzz");
    expect(await screen.findByText("No easy problems match")).toBeInTheDocument();
    await act(async () => { await router.navigate("/problems?q=sum"); });
    expect(screen.getByRole("searchbox", { name: /search problems/i })).toHaveValue("sum");
    expect(await screen.findByText("Two Sum")).toBeInTheDocument();
    expect(screen.queryByText("No easy problems match")).not.toBeInTheDocument();
  });
  it("groups problems into Easy, Medium and Hard tabs with counts", async () => {
    const { user, router } = renderApp("/problems");
    const tabs = await screen.findByRole("tablist", { name: "Difficulty" });
    expect(await within(tabs).findByRole("tab", { name: "Easy 2" })).toHaveAttribute("aria-selected", "true");
    expect(within(tabs).getByRole("tab", { name: "Medium 1" })).toBeInTheDocument();
    expect(within(tabs).getByRole("tab", { name: "Hard 0" })).toBeInTheDocument();
    expect(await screen.findByText("Two Sum")).toBeInTheDocument();
    expect(screen.queryByText("Maximum Subarray Sum")).not.toBeInTheDocument();
    expect(screen.getByText("3 problems")).toBeInTheDocument();

    await user.click(within(tabs).getByRole("tab", { name: "Medium 1" }));
    const row = (await screen.findByText("Maximum Subarray Sum")).closest("a") as HTMLElement;
    expect(within(row).getByText("Medium")).toBeInTheDocument();
    expect(row).toHaveAttribute("href", "/problems/maximum-subarray");
    expect(router.state.location.search).toContain("difficulty=medium");

    await user.click(within(tabs).getByRole("tab", { name: "Hard 0" }));
    expect(await screen.findByText("No hard problems yet")).toBeInTheDocument();
  });

  it("shows five problems per tab, then more on request", async () => {
    const many = Array.from({ length: 23 }, (_, i) => ({
      slug: `p-${i}`, title: `Easy problem ${i + 1}`, difficulty: "easy" as const, topics: ["arrays"], summary: "Practice.",
    }));
    server.use(
      http.get(`${API}/api/v1/problems/counts`, () => HttpResponse.json({ easy: 23, medium: 0, hard: 0 })),
      http.get(`${API}/api/v1/problems`, ({ request }) => {
        const size = Number(new URL(request.url).searchParams.get("page_size"));
        return HttpResponse.json({ items: many.slice(0, size), total: many.length, page: 1, page_size: size });
      }),
    );
    const { user } = renderApp("/problems");
    expect(await screen.findByText("Showing 5 of 23")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Easy problem/ })).toHaveLength(5);
    await user.click(screen.getByRole("button", { name: "View more" }));
    expect(await screen.findByText("Showing 15 of 23")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "View more" }));
    expect(await screen.findByText("Showing 23 of 23")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "View more" })).not.toBeInTheDocument();
  });

  it("points to other levels when a search only matches there", async () => {
    const { user } = renderApp("/problems?q=subarray");
    expect(await screen.findByText("No easy problems match")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "See 1 in Medium" }));
    expect(await screen.findByText("Maximum Subarray Sum")).toBeInTheDocument();
  });

  it("offers example searches", async () => {
    const { user, router } = renderApp("/problems");
    await user.click(await screen.findByRole("button", { name: "two pointers" }));
    expect(router.state.location.search).toContain("q=two+pointers");
    expect(screen.getByRole("searchbox", { name: /search problems/i })).toHaveValue("two pointers");
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
    expect(await screen.findByText("No easy problems match")).toBeInTheDocument();
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
