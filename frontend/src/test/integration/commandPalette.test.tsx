/**
 * The command palette (Volume 10, prompt 1; NAVIGATION.md "Command palette"): Ctrl+K / Cmd+K or the
 * "Go to" button opens a dialog listing pages for this learner (signed in or not, their career,
 * what this server can do); typing filters, arrows move, Enter opens, Escape closes, and focus goes
 * back to what opened it. It never bypasses the unsaved-work guard, never steals the code editor's
 * Ctrl+K or an input method's composition, and one account's recent pages aren't another's.
 */
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { commandsFor, isPaletteShortcut, recentKey, searchCommands } from "@/app/commands";
import { routes } from "@/app/router";
import { matchRoutes } from "react-router-dom";

import { executionStatus, nurseGoals, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asUser = (u: typeof baseUser) => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: u }))));
const palette = () => screen.getByRole("dialog", { name: "Go to a page" });
const field = () => within(palette()).getByRole("combobox", { name: "Go to a page" });
const options = () => within(palette()).queryAllByRole("option").map((o) => o.querySelector(".palette__option-label")?.textContent);
const active = () => {
  const id = field().getAttribute("aria-activedescendant");
  return id ? document.getElementById(id)?.querySelector(".palette__option-label")?.textContent : null;
};
const shortcut = (target: Element = document.body, init: KeyboardEventInit = {}) =>
  fireEvent.keyDown(target, { key: "k", ctrlKey: true, ...init });

describe("the command list", () => {
  const contexts = [true, false].flatMap((signedIn) => [true, false].flatMap((coding) => [true, false].flatMap((demoMode) =>
    [true, false].map((isAdmin) => ({ signedIn, coding, demoMode, isAdmin, executionEnabled: coding })))));

  it("has unique ids and labels in every state, and every command is a page the router has", () => {
    for (const context of contexts) {
      const commands = commandsFor(context);
      expect(new Set(commands.map((c) => c.id)).size, JSON.stringify(context)).toBe(commands.length);
      expect(new Set(commands.map((c) => c.label)).size, JSON.stringify(context)).toBe(commands.length);
      for (const c of commands) {
        const path = c.to.split("?")[0]!;
        const matched = matchRoutes(routes, path)?.at(-1)?.route.path;
        expect(matched, `${c.to} isn't a route`).toBeTruthy();
        expect(matched).not.toBe("*");
      }
    }
  });

  it("shows coding tools only for a coding career, and account pages only when signed in", () => {
    const nurseCommands = commandsFor({ signedIn: true, coding: false, demoMode: false, isAdmin: false, executionEnabled: true });
    expect(nurseCommands.map((c) => c.label)).toEqual(expect.arrayContaining(["Interview questions", "Notes", "My plan", "Start or resume a mock interview"]));
    expect(nurseCommands.map((c) => c.label)).not.toEqual(expect.arrayContaining(["Coding problems"]));
    expect(nurseCommands.find((c) => c.id === "whiteboard")).toBeUndefined();
    const visitor = commandsFor({ signedIn: false, coding: true, demoMode: false, isAdmin: false, executionEnabled: true });
    expect(visitor.map((c) => c.id)).toEqual(["problems", "questions-coding-career", "learn", "help", "sign-in", "register"]);
  });

  it("matches labels and aliases by the start of a word, best first; nothing is sent anywhere", () => {
    const commands = commandsFor({ signedIn: true, coding: true, demoMode: false, isAdmin: false, executionEnabled: true });
    expect(searchCommands(commands, "not")[0]?.label).toBe("Notes");
    expect(searchCommands(commands, "bookmarks")[0]?.label).toBe("Saved");
    expect(searchCommands(commands, "  Mock   INTERVIEW ")[0]?.label).toBe("Start or resume a mock interview");
    expect(searchCommands(commands, "system design").map((c) => c.label)).toEqual(["Whiteboard: explain a design"]);
    expect(searchCommands(commands, "qwxz")).toEqual([]);
    // Plurals either way, and no mid-word matches: "story" isn't "History".
    expect(searchCommands(commands, "story").map((c) => c.label)).toEqual(["Stories", "Write a new story"]);
    expect(searchCommands(commands, "stories").map((c) => c.label)).toEqual(["Stories", "Write a new story"]);
    expect(searchCommands(commands, "note")[0]?.label).toBe("Notes");
  });

  it("the shortcut is Ctrl+K or Cmd+K, not inside the code editor or while composing text", () => {
    const editor = document.createElement("div");
    editor.className = "monaco-editor";
    const inside = document.createElement("textarea");
    editor.appendChild(inside);
    document.body.appendChild(editor);
    const event = (init: KeyboardEventInit, target: Element = document.body) => {
      const e = new KeyboardEvent("keydown", { key: "k", bubbles: true, ...init });
      Object.defineProperty(e, "target", { value: target });
      return e;
    };
    expect(isPaletteShortcut(event({ ctrlKey: true }))).toBe(true);
    expect(isPaletteShortcut(event({ metaKey: true }))).toBe(true);
    expect(isPaletteShortcut(event({ key: "K", ctrlKey: true }))).toBe(true); // caps lock
    expect(isPaletteShortcut(event({ ctrlKey: true, shiftKey: true }))).toBe(false);
    expect(isPaletteShortcut(event({}))).toBe(false);
    expect(isPaletteShortcut(event({ ctrlKey: true }, inside))).toBe(false); // the editor's Ctrl+K chords
    expect(isPaletteShortcut(event({ ctrlKey: true, isComposing: true }))).toBe(false);
    editor.remove();
  });
});

describe("the palette", () => {
  it("opens from the button, filters, moves with the arrows and opens a page; the new page takes focus", async () => {
    asUser(nurse);
    const { user, router } = renderApp("/notes", { signedIn: true });
    await screen.findByRole("heading", { name: "Your notes", level: 1 });
    await user.click(screen.getByRole("button", { name: "Go to…" }));
    expect(field()).toHaveFocus();
    expect(options()).toContain("Interview questions");
    expect(options()).not.toContain("Coding problems"); // a nurse's library isn't called coding
    expect(options()).not.toContain("Whiteboard: explain a design");
    await user.type(field(), "pl");
    expect(options()).toEqual(["My plan"]);
    expect(within(palette()).getByRole("status")).toHaveTextContent("1 page matches.");
    await user.clear(field());
    await user.type(field(), "stories");
    expect(options()).toEqual(["Stories", "Write a new story"]);
    expect(active()).toBe("Stories");
    await user.keyboard("{ArrowDown}");
    expect(active()).toBe("Write a new story");
    await user.keyboard("{ArrowDown}"); // wraps
    expect(active()).toBe("Stories");
    await user.keyboard("{ArrowUp}{Enter}");
    await waitFor(() => expect(router.state.location.pathname).toBe("/stories/new"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(document.getElementById("main")).toHaveFocus());
  });

  it("Ctrl+K opens it from a text field; Escape closes it and puts focus back in that field", async () => {
    asUser(nurse);
    const { user } = renderApp("/notes", { signedIn: true });
    const search = await screen.findByRole("searchbox");
    await user.click(search);
    shortcut(search);
    expect(field()).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(search).toHaveFocus();
    // Close and a click on the backdrop do the same.
    shortcut(search);
    await user.click(within(palette()).getByRole("button", { name: "Close" }));
    expect(search).toHaveFocus();
  });

  it("a page with unsaved work still asks; staying keeps the typing and the place", async () => {
    asUser(nurse);
    server.use(http.get(`${API}/api/v1/me/goals`, () => HttpResponse.json(nurseGoals)));
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    try {
      const { user, router } = renderApp("/plan/goals", { signedIn: true });
      const specialty = await screen.findByLabelText(/Specialty or focus/);
      await user.type(specialty, "Emergency");
      shortcut(specialty);
      await user.type(field(), "notes{Enter}");
      await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1));
      expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/^Your changes to your goals aren't saved/));
      expect(router.state.location.pathname).toBe("/plan/goals");
      expect(specialty).toHaveValue("Emergency");
      expect(specialty).toHaveFocus();
    } finally {
      confirm.mockRestore();
    }
  });

  it("signed out: public pages only; in a coding career the library is called what it is, and a server that doesn't run code says so", async () => {
    const { user } = renderApp("/learn");
    await user.click(await screen.findByRole("button", { name: "Go to…" }));
    await waitFor(() => expect(options()).toEqual(["Coding problems", "Interview questions", "Lessons", "Help", "Sign in", "Create account"]));
    expect(within(palette()).getByText("Code isn't run on this server: attempts are saved, not judged.")).toBeInTheDocument();
  });

  it("on a demo server, Create account explains why it can't open instead of leading to a refusal", async () => {
    server.use(http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({
      execution_enabled: true, ai_provider: "offline", execution: executionStatus("ready"), guest_retention_days: 30, demo_mode: true,
    })));
    const { user, router } = renderApp("/learn");
    await user.click(await screen.findByRole("button", { name: "Go to…" }));
    await waitFor(() => expect(options()).toContain("Guided demo"));
    expect(options()).not.toContain("Sign in");
    await user.type(field(), "create");
    expect(within(palette()).getByRole("option", { name: /Create account/ })).toHaveAttribute("aria-disabled", "true");
    await user.keyboard("{Enter}");
    expect(within(palette()).getByRole("status")).toHaveTextContent("This demo server doesn't create accounts.");
    expect(router.state.location.pathname).toBe("/learn");
    expect(within(palette()).queryByText("Code isn't run on this server", { exact: false })).not.toBeInTheDocument();
  });

  it("no match: says so, Enter does nothing, and the field stays", async () => {
    asUser(nurse);
    const { user, router } = renderApp("/notes", { signedIn: true });
    await screen.findByRole("heading", { name: "Your notes", level: 1 });
    shortcut();
    await user.type(field(), "qwxz{Enter}");
    expect(options()).toEqual([]);
    expect(within(palette()).getByRole("status")).toHaveTextContent("No page matches.");
    expect(within(palette()).getByText("No page matches “qwxz”.")).toBeInTheDocument();
    expect(field()).not.toHaveAttribute("aria-activedescendant");
    expect(router.state.location.pathname).toBe("/notes");
  });

  it("recent pages are this account's: listed first for it, gone when it signs out, never another account's", async () => {
    asUser(nurse);
    const first = renderApp("/notes", { signedIn: true });
    await screen.findByRole("heading", { name: "Your notes", level: 1 });
    shortcut();
    await first.user.type(field(), "applications{Enter}");
    await waitFor(() => expect(first.router.state.location.pathname).toBe("/applications"));
    expect(JSON.parse(localStorage.getItem(recentKey(nurse.id)) ?? "[]")).toEqual(["applications"]);
    shortcut();
    expect(within(palette()).getByRole("group", { name: "Recently used" })).toHaveTextContent("Applications");
    await first.user.keyboard("{Escape}");
    await first.user.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(localStorage.getItem(recentKey(nurse.id))).toBeNull());
    first.unmount();

    // Someone else on this browser, while an old entry of the first account's is still there.
    localStorage.setItem(recentKey(nurse.id), JSON.stringify(["applications"]));
    const other = { ...baseUser, id: "u-2", email: "grace@example.com", display_name: "Grace" };
    asUser(other);
    renderApp("/notes", { signedIn: true });
    await screen.findByRole("heading", { name: "Your notes", level: 1 });
    act(() => { shortcut(); });
    expect(within(palette()).queryByRole("group", { name: "Recently used" })).not.toBeInTheDocument();
  });
});
