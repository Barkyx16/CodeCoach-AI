/**
 * Home shortcuts (Volume 11, prompt 2; docs/SHORTCUTS.md): sensible defaults from the real pages,
 * add, move and remove by keyboard and pointer with focus kept and the new place announced, Reset
 * to defaults changing only the list, kept per account in this browser as page ids only, stored ids
 * checked, a browser that won't store saying so, a career that doesn't offer a page, admin tools
 * never offered, and nothing sent to the account by arranging or opening them.
 */
import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { vi } from "vitest";

import { shortcutsKey } from "@/features/dashboard/shortcuts";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const KEY = shortcutsKey(baseUser.id);
const as = (who: typeof baseUser) => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: who }))));

let requests: string[] = [];
beforeEach(() => {
  requests = [];
  server.events.removeAllListeners();
  server.events.on("request:start", ({ request }) => { requests.push(`${request.method} ${new URL(request.url).pathname}`); });
});
afterEach(() => { server.events.removeAllListeners(); vi.restoreAllMocks(); });

const card = () => screen.findByRole("region", { name: "Your shortcuts" });
const names = (el: HTMLElement) => within(el).getAllByRole("listitem").map((li) => li.querySelector(".shortcut__label, strong")?.textContent);
const writes = () => requests.filter((r) => !r.startsWith("GET") && r !== "POST /api/v1/auth/refresh");
const stored = () => JSON.parse(window.localStorage.getItem(KEY) ?? "null") as unknown;

async function edit(user: ReturnType<typeof renderApp>["user"]) {
  await user.click(within(await card()).getByRole("button", { name: "Edit shortcuts" }));
  return within(await card());
}

describe("Your shortcuts", () => {
  it("starts with defaults that are real pages, opens one without changing anything, and Back comes home", async () => {
    const { user, router } = renderApp("/dashboard", { signedIn: true });
    const section = await card();
    expect(names(section)).toEqual(["Coding problems", "Notes", "Stories", "Applications", "My plan"]);
    const links = within(section).getAllByRole("link");
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["/problems", "/notes", "/stories", "/applications", "/plan"]);
    await waitFor(() => expect(links[0]).toHaveTextContent("Code isn't run on this server")); // the page's own state, said up front
    expect(window.localStorage.getItem(KEY)).toBeNull(); // showing the defaults stores nothing
    await user.click(within(section).getByRole("link", { name: /Notes/ }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/notes"));
    await act(() => router.navigate(-1));
    expect(await card()).toBeInTheDocument();
    expect(writes()).toEqual([]); // opening a shortcut sends, records and spends nothing
  });

  it("adds, moves and removes by keyboard, keeps focus on the moved item, says where it went, and survives a reload", async () => {
    const first = renderApp("/dashboard", { signedIn: true });
    const editor = await edit(first.user);
    expect(editor.getByText(/Kept in this browser for your account/)).toBeInTheDocument();

    await first.user.selectOptions(editor.getByLabelText("Add a shortcut"), "Analytics");
    await first.user.click(editor.getByRole("button", { name: "Add" }));
    expect(editor.getByRole("status")).toHaveTextContent("Analytics added as shortcut 6 of 6.");

    const up = editor.getByRole("button", { name: "Move up: Analytics" });
    act(() => up.focus());
    await first.user.keyboard("{Enter}");
    await first.user.keyboard(" ");
    expect(editor.getByRole("status")).toHaveTextContent("Analytics moved to position 4 of 6.");
    expect(editor.getByRole("button", { name: "Move up: Analytics" })).toHaveFocus(); // the same item, in its new place
    expect(names(editor.getByRole("list"))).toEqual(["Coding problems", "Notes", "Stories", "Analytics", "Applications", "My plan"]);

    const firstUp = editor.getByRole("button", { name: "Move up: Coding problems" });
    expect(firstUp).toHaveAttribute("aria-disabled", "true");
    act(() => firstUp.focus());
    await first.user.keyboard("{Enter}");
    expect(editor.getByRole("status")).toHaveTextContent("Coding problems is already first.");
    expect(firstUp).toHaveFocus(); // a boundary press doesn't drop focus

    await first.user.click(editor.getByRole("button", { name: "Remove Stories" }));
    expect(editor.getByRole("status")).toHaveTextContent("Stories removed. 5 shortcuts left.");
    expect(editor.getByRole("button", { name: "Remove Analytics" })).toHaveFocus(); // the next item takes it

    await first.user.click(editor.getByRole("button", { name: "Done" }));
    expect(screen.getByRole("button", { name: "Edit shortcuts" })).toHaveFocus();
    expect(stored()).toEqual({ v: 1, ids: ["library", "notes", "analytics", "applications", "plan"] }); // ids only
    first.unmount();

    renderApp("/dashboard", { signedIn: true });
    expect(names(await card())).toEqual(["Coding problems", "Notes", "Analytics", "Applications", "My plan"]);
    expect(writes()).toEqual([]); // the account isn't touched
  });

  it("Reset to defaults only changes the list", async () => {
    window.localStorage.setItem(KEY, JSON.stringify({ v: 1, ids: ["history", "notes"] }));
    const { user } = renderApp("/dashboard", { signedIn: true });
    expect(names(await card())).toEqual(["History", "Notes"]);
    const editor = await edit(user);
    expect(editor.getByText(/Reset puts back Coding problems, Notes, Stories, Applications and My plan\. It only changes this list\./)).toBeInTheDocument();
    await user.click(editor.getByRole("button", { name: "Reset to defaults" }));
    expect(editor.getByRole("status")).toHaveTextContent("Shortcuts are back to the defaults. Nothing else changed.");
    expect(editor.getByRole("button", { name: "Reset to defaults" })).toHaveFocus();
    expect(window.localStorage.getItem(KEY)).toBeNull();
    expect(names(editor.getByRole("list"))).toEqual(["Coding problems", "Notes", "Stories", "Applications", "My plan"]);
    expect(writes()).toEqual([]);
  });

  it("leaves out stored ids it doesn't offer, and never shows a stored URL or admin tool", async () => {
    window.localStorage.setItem(KEY, JSON.stringify({ v: 1, ids: ["notes", "triage", "https://evil.example", "javascript:alert(1)", "notes", 7, "plan"] }));
    const first = renderApp("/dashboard", { signedIn: true });
    const section = await card();
    expect(names(section)).toEqual(["Notes", "My plan"]);
    expect(section).toHaveTextContent("5 saved shortcuts are no longer offered, so they aren't shown.");
    expect(within(section).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual(["/notes", "/plan"]);
    first.unmount();

    window.localStorage.setItem(KEY, "{not json");
    renderApp("/dashboard", { signedIn: true });
    expect(await card()).toHaveTextContent("Your saved shortcuts couldn't be read, so the defaults are shown.");
    expect(names(await card())).toHaveLength(5);
  });

  it("doesn't offer admin tools, even to an admin", async () => {
    as({ ...baseUser, is_admin: true });
    const { user } = renderApp("/dashboard", { signedIn: true });
    const editor = await edit(user);
    const options = within(editor.getByLabelText("Add a shortcut")).getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("Analytics");
    expect(options).not.toContain("Triage reports");
    expect(options).not.toContain("Dashboard");
    expect(options).not.toContain("Sign in");
  });

  it("says so when this browser won't keep the change, and doesn't pretend it was saved", async () => {
    const first = renderApp("/dashboard", { signedIn: true });
    const editor = await edit(first.user);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
    await first.user.click(editor.getByRole("button", { name: "Move up: Notes" }));
    expect(editor.getByRole("status")).toHaveTextContent("Notes moved to position 1 of 5. This browser didn't keep it, so the change lasts only until you leave this page.");
    await first.user.click(editor.getByRole("button", { name: "Done" }));
    expect(await card()).toHaveTextContent("This browser didn't keep it");
    expect(names(await card())[0]).toBe("Notes"); // it still applies here
    vi.restoreAllMocks();
    first.unmount();
    renderApp("/dashboard", { signedIn: true });
    expect(names(await card())[0]).toBe("Coding problems"); // and wasn't kept
  });

  it("keeps a page the current career doesn't offer understandable, and doesn't offer it to add", async () => {
    as({ ...baseUser, career_track: "registered-nurse" });
    window.localStorage.setItem(KEY, JSON.stringify({ v: 1, ids: ["whiteboard", "library", "notes"] }));
    const { user } = renderApp("/dashboard", { signedIn: true });
    const section = await card();
    await waitFor(() => expect(names(section)).toEqual(["Whiteboard: explain a design", "Interview questions", "Notes"]));
    expect(section).toHaveTextContent("Not part of Registered Nurse practice.");
    expect(within(section).queryByRole("link", { name: /Whiteboard/ })).not.toBeInTheDocument(); // not a link to nowhere
    expect(within(section).getByRole("link", { name: /Interview questions/ })).toHaveAttribute("href", "/problems");
    const editor = await edit(user);
    const options = within(editor.getByLabelText("Add a shortcut")).getAllByRole("option").map((o) => o.textContent);
    expect(options).not.toContain("Whiteboard: explain a design");
    expect(options).not.toContain("Debugging lab");
    await user.click(editor.getByRole("button", { name: "Remove Whiteboard: explain a design" }));
    expect(stored()).toEqual({ v: 1, ids: ["library", "notes"] });
  });

  it("shows a change made in another tab of this browser", async () => {
    renderApp("/dashboard", { signedIn: true });
    expect(names(await card())).toHaveLength(5);
    window.localStorage.setItem(KEY, JSON.stringify({ v: 1, ids: ["goals"] }));
    act(() => { window.dispatchEvent(new StorageEvent("storage", { key: KEY })); });
    expect(names(await card())).toEqual(["Goals"]);
  });

  it("another account on this browser has its own list and leaves the first one's alone", async () => {
    const bea = { ...baseUser, id: "u-bea", email: "bea@example.com", display_name: "Bea" };
    window.localStorage.setItem(KEY, JSON.stringify({ v: 1, ids: ["history"] }));
    server.use(http.post(`${API}/api/v1/auth/login`, () => HttpResponse.json(tokenResponse({ user: bea }))));
    const { user, router } = renderApp("/dashboard", { signedIn: true });
    expect(names(await card())).toEqual(["History"]);
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(router.state.location.pathname).not.toBe("/dashboard"));
    await act(() => router.navigate("/login"));
    await user.type(await screen.findByLabelText("Email"), bea.email);
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.state.location.pathname).not.toBe("/login"));
    await act(() => router.navigate("/dashboard"));
    expect(names(await card())).toEqual(["Coding problems", "Notes", "Stories", "Applications", "My plan"]);
    const editor = await edit(user);
    await user.click(editor.getByRole("button", { name: "Remove Stories" }));
    expect(JSON.parse(window.localStorage.getItem(shortcutsKey("u-bea"))!)).toEqual({ v: 1, ids: ["library", "notes", "applications", "plan"] });
    expect(stored()).toEqual({ v: 1, ids: ["history"] }); // Ada's list is Ada's
  });
});
