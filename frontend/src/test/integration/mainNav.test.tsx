import { screen, waitFor, within } from "@testing-library/react";

import { renderApp } from "../render";

const nav = () => screen.getByRole("navigation", { name: "Main" });
const heading = (name: string) => within(nav()).getByRole("button", { name });

describe("the main navigation", () => {
  it("groups the pages under four headings, each a button that opens its panel", async () => {
    const { user } = renderApp("/problems", { signedIn: true });
    await waitFor(() => expect(heading("Progress")).toBeInTheDocument());
    expect(within(nav()).getAllByRole("button").map((b) => b.textContent)).toEqual(["Practice", "Progress", "Job search", "Library"]);

    const progress = heading("Progress");
    expect(progress).toHaveAttribute("aria-expanded", "false");
    await user.click(progress);
    expect(progress).toHaveAttribute("aria-expanded", "true");
    const panel = document.getElementById(progress.getAttribute("aria-controls")!)!;
    const dashboard = within(panel).getByRole("link", { name: "Dashboard" });
    expect(dashboard).toHaveAccessibleDescription("Today's plan and where you stand");
    expect(within(panel).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual(["/dashboard", "/analytics", "/history"]);

    await user.click(progress); // a second click closes it
    expect(progress).toHaveAttribute("aria-expanded", "false");
  });

  it("Escape closes the open panel and puts focus back on its heading", async () => {
    const { user } = renderApp("/problems", { signedIn: true });
    await waitFor(() => expect(heading("Library")).toBeInTheDocument());
    await user.click(heading("Library"));
    await user.tab(); // into the panel
    expect(document.activeElement).toHaveTextContent("Stories");
    await user.keyboard("{Escape}");
    expect(heading("Library")).toHaveAttribute("aria-expanded", "false");
    expect(heading("Library")).toHaveFocus();
  });

  it("choosing a page closes the panel and marks its heading as the current section", async () => {
    const { user, router } = renderApp("/problems", { signedIn: true });
    await waitFor(() => expect(heading("Job search")).toBeInTheDocument());
    await user.click(heading("Job search"));
    await user.click(within(nav()).getByRole("link", { name: "Applications" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/applications"));
    expect(heading("Job search")).toHaveAttribute("aria-expanded", "false");
    expect(heading("Job search").closest(".nav-group")).toHaveClass("is-current");
    expect(within(nav()).getByRole("link", { name: "Applications" })).toHaveAttribute("aria-current", "page");
  });

  it("signed out, only practice is offered, with what works without an account", async () => {
    renderApp("/");
    await waitFor(() => expect(heading("Practice")).toBeInTheDocument());
    expect(within(nav()).getAllByRole("button")).toHaveLength(1);
    expect(within(nav()).getAllByRole("link").map((a) => a.textContent)).toEqual([
      expect.stringContaining("Questions"), expect.stringContaining("Lessons"),
    ]);
  });
});
