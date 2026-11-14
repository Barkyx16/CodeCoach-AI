import { screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import type { CollectionItem } from "@/api/types";

import { DEFAULT_DISPLAY, DISPLAY_KEY, parseDisplayPrefs } from "@/features/display/displayPrefs";
import { DEFAULT_VOICE_PREFS, parseVoicePrefs } from "@/features/voice/voicePrefs";

import { store as explore } from "../explore";
import { renderApp } from "../render";

const html = document.documentElement;

describe("display preferences", () => {
  it("validates saved values field by field and ignores anything unknown", () => {
    expect(parseDisplayPrefs(null)).toEqual(DEFAULT_DISPLAY);
    expect(parseDisplayPrefs("not json")).toEqual(DEFAULT_DISPLAY);
    expect(parseDisplayPrefs("[1,2]")).toEqual(DEFAULT_DISPLAY);
    expect(parseDisplayPrefs(JSON.stringify({ theme: "light", text: "huge", contrast: "high", motion: 1, spacing: "spacious", extra: "x" })))
      .toEqual({ ...DEFAULT_DISPLAY, theme: "light", contrast: "high", spacing: "spacious" });
  });

  it("applies choices to the page at once, saves them in this browser and resets to defaults", async () => {
    const { user } = renderApp("/settings", { signedIn: true });
    const section = await screen.findByRole("region", { name: "Display & reading" });
    expect(within(section).getByRole("status")).toHaveTextContent("Saved in this browser.");
    expect(within(section).getByRole("button", { name: "Reset to defaults" })).toBeDisabled();

    await user.click(within(section).getByRole("radio", { name: "Light" }));
    await user.click(within(section).getByRole("radio", { name: "Higher" }));
    await user.click(within(section).getByRole("radio", { name: "Larger" }));
    await user.click(within(section).getByRole("radio", { name: "Spacious" }));
    await user.click(within(section).getByRole("radio", { name: "Reduce" }));
    expect(html).toHaveAttribute("data-theme", "light");
    expect(html).toHaveAttribute("data-contrast", "high");
    expect(html).toHaveAttribute("data-text", "larger");
    expect(html).toHaveAttribute("data-spacing", "spacious");
    expect(html).toHaveAttribute("data-motion", "reduce");
    expect(JSON.parse(localStorage.getItem(DISPLAY_KEY)!)).toEqual({ theme: "light", contrast: "high", text: "larger", spacing: "spacious", motion: "reduce" });

    // Keyboard: arrow keys move within a group like any radio group.
    within(section).getByRole("radio", { name: "Larger" }).focus();
    await user.keyboard("{ArrowLeft}");
    expect(within(section).getByRole("radio", { name: "Large" })).toBeChecked();
    expect(html).toHaveAttribute("data-text", "large");

    await user.click(within(section).getByRole("button", { name: "Reset to defaults" }));
    expect(localStorage.getItem(DISPLAY_KEY)).toBeNull();
    for (const name of ["data-text", "data-contrast", "data-spacing", "data-motion"]) expect(html).not.toHaveAttribute(name);
    expect(html).toHaveAttribute("data-theme", "dark"); // "Match device"; jsdom has no light-mode preference
    expect(within(section).getByRole("radio", { name: "Match device" })).toBeChecked();
  });

  it("starts from saved values and falls back to defaults for invalid ones", async () => {
    localStorage.setItem(DISPLAY_KEY, JSON.stringify({ theme: "light", text: "gigantic", contrast: "high" }));
    renderApp("/settings", { signedIn: true });
    const section = await screen.findByRole("region", { name: "Display & reading" });
    expect(within(section).getByRole("radio", { name: "Light" })).toBeChecked();
    expect(within(section).getByRole("radio", { name: "Higher" })).toBeChecked();
    expect(within(section).getByRole("radio", { name: "Default" })).toBeChecked();
    expect(html).toHaveAttribute("data-theme", "light");
    expect(html).not.toHaveAttribute("data-text");
  });

  it("says honestly when this browser won't store them, and still applies them for the visit", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
    try {
      const { user } = renderApp("/settings", { signedIn: true });
      const section = await screen.findByRole("region", { name: "Display & reading" });
      expect(within(section).getByRole("status")).toHaveTextContent("won't store settings");
      await user.click(within(section).getByRole("radio", { name: "Light" }));
      expect(html).toHaveAttribute("data-theme", "light");
      expect(within(section).getByRole("status")).toHaveTextContent("apply for this visit only");
    } finally {
      setItem.mockRestore();
    }
  });

  it("voice settings are validated too: a corrupted value never turns on reading aloud", () => {
    expect(parseVoicePrefs(JSON.stringify({ readAloud: "yes", rate: 99, volume: -1, voiceURI: 5, captions: false }))).toEqual({ ...DEFAULT_VOICE_PREFS, captions: false });
    expect(parseVoicePrefs("{oops")).toEqual(DEFAULT_VOICE_PREFS);
    expect(parseVoicePrefs(JSON.stringify({ readAloud: true, rate: 1.2 }))).toMatchObject({ readAloud: true, rate: 1.2 });
  });
});

describe("focus mode", () => {
  it("hides navigation and extras, keeps the draft and the essentials, and returns focus when you exit", async () => {
    const { user } = renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    await screen.findByRole("heading", { name: "Patient assessment under pressure", level: 1 });
    await user.type(screen.getByLabelText("Your answer"), "Last winter I led a rapid response.");
    const toggle = screen.getByRole("button", { name: "Focus mode" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");

    await user.click(toggle);
    expect(html).toHaveAttribute("data-focus");
    expect(screen.queryByRole("navigation", { name: "Main" })).toBeNull(); // the site navigation is gone
    expect(screen.getByText(/navigation and side panels are hidden/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Focus mode" })).toHaveAttribute("aria-pressed", "true"); // same control, now pressed
    // Essentials stay: the question, the answer (with the draft), the submit button and the tips.
    expect(screen.getByLabelText("Your answer")).toHaveValue("Last winter I led a rapid response.");
    expect(screen.getByRole("button", { name: "Get feedback" })).toBeEnabled();
    expect(screen.getByText("Use the STAR method.")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Breadcrumb" }).closest(".focus-hide")).not.toBeNull();

    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Exit focus mode" }));
    expect(html).not.toHaveAttribute("data-focus");
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Focus mode" })).toHaveFocus());
    expect(screen.getByLabelText("Your answer")).toHaveValue("Last winter I led a rapid response.");
  });

  it("Escape exits (outside the code editor), and leaving the page ends it", async () => {
    const { user, router } = renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    await screen.findByRole("heading", { name: "Patient assessment under pressure", level: 1 });
    await user.click(screen.getByRole("button", { name: "Focus mode" }));
    await user.click(screen.getByLabelText("Your answer"));
    await user.keyboard("{Escape}");
    expect(html).not.toHaveAttribute("data-focus");
    await waitFor(() => expect(screen.getByRole("button", { name: "Focus mode" })).toHaveFocus());

    await user.click(screen.getByRole("button", { name: "Focus mode" }));
    expect(html).toHaveAttribute("data-focus");
    // Not even for a moment: the next page never appears in this page's focus mode (a full test run
    // once found its heading before the mode had ended).
    const whenShown: boolean[] = [];
    const watch = new MutationObserver(() => {
      if (!whenShown.length && document.querySelector("h1")?.textContent === "Your notes") whenShown.push(html.hasAttribute("data-focus"));
    });
    watch.observe(document.body, { childList: true, subtree: true, characterData: true });
    await router.navigate("/notes");
    await screen.findByRole("heading", { name: "Your notes", level: 1 });
    watch.disconnect();
    expect(whenShown).toEqual([false]);
    expect(html).not.toHaveAttribute("data-focus");
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  });
});

describe("focus after removals", () => {
  it("removing a bookmark moves focus to the list heading and announces it; a failure is shown, not lost", async () => {
    explore.bookmarks = [
      { item_type: "question", track: "registered-nurse", ref_id: "m-pressure-0", title: "Patient assessment under pressure", href: "/careers/registered-nurse/questions/m-pressure-0", available: true, created_at: new Date().toISOString() },
      { item_type: "question", track: "registered-nurse", ref_id: "e-good-0", title: "What makes a good nurse", href: "/careers/registered-nurse/questions/e-good-0", available: true, created_at: new Date().toISOString() },
    ];
    const { user } = renderApp("/saved", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Remove bookmark: Patient assessment under pressure" }));
    expect(screen.getByRole("heading", { name: "Bookmarks", level: 2 })).toHaveFocus();
    await waitFor(() => expect(screen.getByText("Removed bookmark: Patient assessment under pressure.")).toBeInTheDocument());

    explore.failBookmarks = true;
    await user.click(screen.getByRole("button", { name: "Remove bookmark: What makes a good nurse" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The service is busy. Try again.");
    expect(screen.getByRole("button", { name: "Remove bookmark: What makes a good nurse" })).toBeInTheDocument(); // it came back
  });

  it("removing a collection item focuses the next item's Remove; Cancel on delete returns to the Delete button", async () => {
    const item = (n: number, ref_id: string, title: string): CollectionItem => ({
      id: `i-${n}`, item_type: "question", track: "registered-nurse", ref_id, position: n, title, href: `/careers/registered-nurse/questions/${ref_id}`,
      available: true, unavailable_reason: null, queue_done: false, practiced_since_added: false,
    });
    explore.collections = [{
      id: "c-1", name: "Week 1", items: 2, queue_position: 0, queue_started: false, updated_at: new Date().toISOString(), queue_done: 0, contains: null,
      item_list: [item(0, "m-pressure-0", "Patient assessment under pressure"), item(1, "e-good-0", "What makes a good nurse")],
    }];
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Remove “Patient assessment under pressure” from this collection" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Remove “What makes a good nurse” from this collection" })).toHaveFocus());
    expect(screen.getByText("Removed “Patient assessment under pressure” from this collection.")).toBeInTheDocument();
    // The last one: focus goes to the collection's title.
    await user.click(screen.getByRole("button", { name: "Remove “What makes a good nurse” from this collection" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Week 1", level: 1 })).toHaveFocus());

    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("alertdialog", { name: "Delete “Week 1”?" });
    expect(within(dialog).getByRole("button", { name: "Delete collection" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).toBeNull();
    await waitFor(() => expect(screen.getByRole("button", { name: "Delete" })).toHaveFocus());
  });
});
