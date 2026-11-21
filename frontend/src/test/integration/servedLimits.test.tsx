/**
 * The limits forms state are the server's, as it serves them (Volume 17, prompt 7; docs/API.md,
 * "Limits"). Each check serves a number unlike this build's, so a form stating a copy of its own
 * fails; and makes the read fail, so the form states no number and leaves the deciding to the server.
 * Here: a collection's Duplicate, its bulk bar and its copy-or-move form, and the saved list's bulk bar.
 * The other forms are checked beside their own tests (restore, targets, goals, packet, sharing,
 * whiteboard, applications, the question page).
 */
import { screen, waitFor, within } from "@testing-library/react";

import type { Bookmark, Collection } from "@/api/types";

import { resetExploreStore, store } from "../explore";
import { failLimits, serveLimits } from "../limits";
import { renderApp } from "../render";

const now = () => new Date().toISOString();
const collection = (id: string, name: string, n: number): Collection => ({
  id, name, items: n, queue_position: 0, queue_started: false, updated_at: now(), queue_done: 0, contains: null,
  item_list: Array.from({ length: n }, (_, i) => ({
    id: `${id}-i${i}`, item_type: "question" as const, track: "registered-nurse", ref_id: `q-${id}-${i}`, position: i, title: `Question ${i + 1}`,
    href: `/careers/registered-nurse/questions/q-${i}`, available: true, unavailable_reason: null, queue_done: false, practiced_since_added: false,
  })),
});
const mark = (ref_id: string, title: string): Bookmark => ({
  id: `b-${ref_id}`, item_type: "question", track: "registered-nurse", ref_id, title, href: `/careers/registered-nurse/questions/${ref_id}`,
  available: true, unavailable_reason: null, content_version: 1, created_at: now(),
});

beforeEach(() => resetExploreStore());

describe("A collection's forms state the server's limits", () => {
  it("Duplicate states the served number of collections, and is held back at it", async () => {
    store.collections = [collection("c-1", "Week 1", 1), collection("c-2", "Week 2", 0), collection("c-3", "Week 3", 0)];
    serveLimits({ collections_per_account: 3 });
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Duplicate" }));
    const form = screen.getByRole("form", { name: "Duplicate “Week 1”" });
    expect(await within(form).findByRole("status", {}, { timeout: 3000 })).toHaveTextContent("You have 3 of 3 collections: delete one to make room for a copy.");
    expect(within(form).getByRole("button", { name: "Make the copy" })).toBeDisabled();
  });

  it("Duplicate states no number when the limits can't be read, and the server decides", async () => {
    store.collections = [collection("c-1", "Week 1", 1), collection("c-2", "Week 2", 0), collection("c-3", "Week 3", 0)];
    const reads = failLimits();
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Duplicate" }));
    await waitFor(() => expect(reads.n).toBe(2), { timeout: 4000 });
    const form = screen.getByRole("form", { name: "Duplicate “Week 1”" });
    expect(form).not.toHaveTextContent(/of \d+ collections/);
    expect(within(form).getByRole("button", { name: "Make the copy" })).toBeEnabled();
  });

  it("the bulk bar and the copy-or-move form state the served batch size and room", async () => {
    store.collections = [collection("c-1", "Week 1", 3), collection("c-2", "Week 2", 1)];
    serveLimits({ items_per_batch: 2, items_per_collection: 4 });
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    await user.click(await screen.findByRole("checkbox", { name: "Select all shown (3)" }));
    expect(await screen.findByText("Up to 2 at a time: 3 are selected.", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Move 3 to…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Remove 3 from “Week 1”" })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: "Select: Question 3" }));
    await user.click(screen.getByRole("button", { name: "Move 2 to…" }));
    const form = screen.getByRole("form", { name: "Move 2 items to another collection" });
    await user.selectOptions(within(form).getByLabelText("To collection"), "c-2");
    expect(await within(form).findByText("It has room for 3 more.", {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it("with the limits unread, neither the batch size nor the room is stated", async () => {
    store.collections = [collection("c-1", "Week 1", 3), collection("c-2", "Week 2", 1)];
    const reads = failLimits();
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    await user.click(await screen.findByRole("checkbox", { name: "Select all shown (3)" }));
    await waitFor(() => expect(reads.n).toBe(2), { timeout: 4000 });
    expect(screen.queryByText(/Up to \d+ at a time/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Move 3 to…" }));
    const form = screen.getByRole("form", { name: "Move 3 items to another collection" });
    await user.selectOptions(within(form).getByLabelText("To collection"), "c-2");
    const words = await within(form).findByRole("list", { name: "Before you move them" });
    expect(words).toHaveTextContent("“Week 2” has none of these 3 yet.");
    expect(words).not.toHaveTextContent(/room|full|fit/);
  });
});

describe("The saved list's bulk bar states the server's batch size", () => {
  it("states the served number, and none when the read fails", async () => {
    store.bookmarks = [mark("e-good-0", "What good patient assessment looks like"), mark("e-time-0", "A time patient assessment mattered")];
    store.collections = [collection("c-1", "Week 1", 0)];
    serveLimits({ items_per_batch: 1 });
    const { user, unmount } = renderApp("/saved", { signedIn: true });
    const bar = await screen.findByRole("group", { name: "Selected bookmarks" });
    await user.click(within(bar).getByRole("checkbox", { name: "Select all shown (2)" }));
    expect(await screen.findByText("Up to 1 at a time: 2 are selected.", {}, { timeout: 3000 })).toBeInTheDocument();
    unmount();

    const reads = failLimits();
    const again = renderApp("/saved", { signedIn: true });
    const bar2 = await screen.findByRole("group", { name: "Selected bookmarks" });
    await again.user.click(within(bar2).getByRole("checkbox", { name: "Select all shown (2)" }));
    await waitFor(() => expect(reads.n).toBe(2), { timeout: 4000 });
    expect(screen.queryByText(/Up to \d+ at a time/)).not.toBeInTheDocument();
  });
});

describe("Pages that state no limit don't ask for them", () => {
  it("the dashboard never asks; a problem's page asks only once its report form is opened", async () => {
    const reads = serveLimits({});
    const dash = renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1 }, { timeout: 3000 })).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 300));
    expect(reads.n).toBe(0);
    dash.unmount();
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await screen.findByRole("tab", { name: "Code review" }, { timeout: 3000 });
    await new Promise((r) => setTimeout(r, 300));
    expect(reads.n).toBe(0); // the report form is there, closed
    await user.click(screen.getByRole("button", { name: "Report an issue" }));
    await waitFor(() => expect(reads.n).toBe(1));
  });
});
