/**
 * What's new with hostile or unfinished content (docs/WHATS_NEW.md): markup in an entry is shown
 * as text and never runs; an entry pointing at a URL or an unknown page isn't shown; an entry for a
 * later release than this build's isn't shown, so a planned change can't appear as shipped.
 */
import { screen, within } from "@testing-library/react";

import type { ReleaseEntry } from "@/features/whatsnew/releases";

import { renderApp } from "../render";

vi.mock("@/features/whatsnew/releases", () => {
  const base = { where: "Somewhere.", what: "Plain words." };
  const entries: (ReleaseEntry | Record<string, unknown>)[] = [
    { ...base, id: "markup", release: 2, opens: "packet",
      title: '<img src=x onerror="window.__pwned=1">Shiny', what: "<script>window.__pwned=1</script> It got <b>better</b>.",
      where: "[here](javascript:window.__pwned=1)", limit: "<a href=\"https://example.com\">more</a>" },
    { ...base, id: "script-url", release: 2, opens: "javascript:window.__pwned=1", title: "Pointing at a script" },
    { ...base, id: "outside", release: 2, opens: "https://example.com/", title: "Pointing elsewhere" },
    { ...base, id: "planned", release: 3, opens: "packet", title: "Planned, not built" },
    { ...base, id: "real", release: 1, opens: "help", title: "Go to any page by typing" },
  ];
  return { ENTRIES: entries, RELEASES: [{ release: 3, title: "Next" }, { release: 2, title: "Now" }, { release: 1, title: "Before" }] };
});

describe("What's new content", () => {
  it("shows markup as text, never runs it, and leaves out bad links and later releases", async () => {
    renderApp("/whats-new");
    const shiny = await screen.findByRole("heading", { level: 3, name: '<img src=x onerror="window.__pwned=1">Shiny' }, { timeout: 3000 });
    const item = shiny.closest("li")!;
    expect(item).toHaveTextContent("<script>window.__pwned=1</script> It got <b>better</b>.");
    expect(item).toHaveTextContent("[here](javascript:window.__pwned=1)");
    expect(item.querySelector("img, script, b, a[href^='https://'], a[href^='javascript:']")).toBeNull();
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined();
    expect(screen.queryByText("Pointing at a script")).toBeNull();
    expect(screen.queryByText("Pointing elsewhere")).toBeNull();
    expect(screen.queryByText("Planned, not built")).toBeNull();
    expect(screen.queryByRole("heading", { name: /Next/ })).toBeNull();
    expect(screen.getByRole("heading", { level: 2, name: "In this version: Now" })).toBeInTheDocument();
    const earlier = screen.getByRole("region", { name: "Earlier: Before" });
    expect(within(earlier).getByRole("link", { name: "Open Help" })).toHaveAttribute("href", "/help");
  });
});
