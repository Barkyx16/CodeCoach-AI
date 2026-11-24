import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";

import { DEFAULT_DISPLAY, DISPLAY_KEY, parseDisplayPrefs } from "@/features/display/displayPrefs";

import { renderApp } from "../render";

const html = document.documentElement;
const realMatchMedia = window.matchMedia;

/** A window wider than 1100px (where the sidebar, and so the rail, exists) or narrower. */
function windowIsWide(wide: boolean) {
  window.matchMedia = ((q: string) => ({
    matches: q.includes("min-width: 1101px") ? wide : false, media: q, onchange: null,
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false,
  })) as typeof window.matchMedia;
}

const tip = () => document.querySelector(".rail-tip");

afterEach(() => {
  window.matchMedia = realMatchMedia;
  html.removeAttribute("data-sidebar");
});

describe("the sidebar's icon rail", () => {
  it("is a display preference: validated, defaulting to the full sidebar", () => {
    expect(DEFAULT_DISPLAY.sidebar).toBe("full");
    expect(parseDisplayPrefs(JSON.stringify({ sidebar: "icons" })).sidebar).toBe("icons");
    expect(parseDisplayPrefs(JSON.stringify({ sidebar: "tiny" })).sidebar).toBe("full");
  });

  it("collapses and expands from the sidebar's own button, remembered in this browser, every page still named", async () => {
    windowIsWide(true);
    const { user } = renderApp("/dashboard", { signedIn: true });
    const collapse = await screen.findByRole("button", { name: "Collapse sidebar" });
    expect(html).not.toHaveAttribute("data-sidebar");

    await user.click(collapse);
    expect(html).toHaveAttribute("data-sidebar", "icons");
    expect(JSON.parse(localStorage.getItem(DISPLAY_KEY)!)).toMatchObject({ sidebar: "icons" });
    // The same button, renamed, keeps focus: pressing it again undoes it.
    const expand = screen.getByRole("button", { name: "Expand sidebar" });
    expect(expand).toHaveFocus();
    // Labels are clipped, not removed: every control keeps its name.
    const nav = screen.getByRole("navigation", { name: "Main" });
    for (const name of ["Questions", "Mock interview", "Dashboard", "Analytics", "History", "Applications", "Notes"]) {
      expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: "New mock interview" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Help" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();

    await user.click(expand);
    expect(html).not.toHaveAttribute("data-sidebar");
    expect(localStorage.getItem(DISPLAY_KEY)).toBeNull(); // back to every default: nothing kept
    expect(screen.getByRole("button", { name: "Collapse sidebar" })).toHaveFocus();
  });

  it("shows a control's name beside the rail on keyboard focus and hover; Escape and leaving dismiss it", async () => {
    windowIsWide(true);
    localStorage.setItem(DISPLAY_KEY, JSON.stringify({ sidebar: "icons" }));
    const { user } = renderApp("/dashboard", { signedIn: true });
    const nav = await screen.findByRole("navigation", { name: "Main" });
    const analytics = within(nav).getByRole("link", { name: "Analytics" });

    act(() => analytics.focus());
    expect(tip()).toHaveTextContent("Analytics");
    expect(tip()).toHaveAttribute("aria-hidden", "true"); // the link already has this name
    await user.keyboard("{Escape}");
    expect(tip()).toBeNull();

    const help = screen.getByRole("link", { name: "Help" });
    act(() => { fireEvent.pointerOver(help); });
    expect(tip()).toHaveTextContent("Help");
    act(() => { fireEvent.pointerOut(help); });
    await waitFor(() => expect(tip()).toBeNull());

    // Focus moving on to the page takes it away.
    act(() => screen.getByRole("button", { name: "Expand sidebar" }).focus());
    expect(tip()).toHaveTextContent("Expand sidebar");
    act(() => (document.getElementById("main") as HTMLElement).focus());
    expect(tip()).toBeNull();
  });

  it("shows no floating names where the labels are on screen: the full sidebar, or a narrow window", async () => {
    windowIsWide(true);
    renderApp("/dashboard", { signedIn: true });
    const nav = await screen.findByRole("navigation", { name: "Main" });
    act(() => within(nav).getByRole("link", { name: "History" }).focus());
    expect(tip()).toBeNull();
  });

  it("isn't offered as a rail on a narrow window, even when chosen", async () => {
    windowIsWide(false);
    localStorage.setItem(DISPLAY_KEY, JSON.stringify({ sidebar: "icons" }));
    renderApp("/dashboard", { signedIn: true });
    const nav = await screen.findByRole("navigation", { name: "Main" });
    act(() => within(nav).getByRole("link", { name: "History" }).focus());
    expect(tip()).toBeNull();
  });

  it("is also a choice in Settings › Display", async () => {
    windowIsWide(true);
    const { user } = renderApp("/settings", { signedIn: true });
    const section = await screen.findByRole("region", { name: "Display & reading" });
    const sidebar = within(section).getByRole("group", { name: "Sidebar" });
    expect(within(sidebar).getByRole("radio", { name: "Full" })).toBeChecked();
    await user.click(within(sidebar).getByRole("radio", { name: "Icons only" }));
    expect(html).toHaveAttribute("data-sidebar", "icons");
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeInTheDocument();
  });
});
