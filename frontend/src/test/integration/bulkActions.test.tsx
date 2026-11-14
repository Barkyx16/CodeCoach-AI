/**
 * Several saved items at once (Volume 11, prompt 5; docs/BULK_ACTIONS.md): the selection covers only
 * the rows shown and says how many; adding to a collection and removing from one report what
 * happened to each item, with the ones that need attention kept selected; a lost reply is sent again
 * safely and reports what was already done; removing leaves bookmarks alone; at most 50 at a time.
 */
import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Bookmark, Collection } from "@/api/types";

import { resetExploreStore, store } from "../explore";
import { tokenResponse, user } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const now = () => new Date().toISOString();
const mark = (ref_id: string, title: string): Bookmark => ({
  item_type: "question", track: "registered-nurse", ref_id, title, href: `/careers/registered-nurse/questions/${ref_id}`,
  available: true, unavailable_reason: null, content_version: 1, created_at: now(),
});
const collection = (id: string, name: string, refs: { id: string; ref_id: string; title: string }[] = []): Collection => ({
  id, name, items: refs.length, queue_position: 0, queue_started: false, updated_at: now(), queue_done: 0, contains: null,
  item_list: refs.map((r, n) => ({ id: r.id, item_type: "question", track: "registered-nurse", ref_id: r.ref_id, position: n, title: r.title,
    href: `/careers/registered-nurse/questions/${r.ref_id}`, available: true, unavailable_reason: null, queue_done: false, practiced_since_added: false })),
});

let sent: { method: string; path: string; body: unknown }[] = [];
beforeEach(() => {
  resetExploreStore();
  sent = [];
  server.events.removeAllListeners();
  server.events.on("request:start", async ({ request }) => {
    if (request.method === "GET" || request.url.endsWith("/auth/refresh")) return;
    sent.push({ method: request.method, path: new URL(request.url).pathname, body: await request.clone().json().catch(() => null) });
  });
});
afterEach(() => { server.events.removeAllListeners(); });

describe("Adding several bookmarks to a collection", () => {
  it("selects only what's shown, adds them, and says what happened to each", async () => {
    store.bookmarks = [mark("e-good-0", "What good patient assessment looks like"), mark("e-time-0", "A time patient assessment mattered"), mark("gone-1", "A retired question")];
    store.collections = [collection("c-1", "Week 1")];
    const { user } = renderApp("/saved", { signedIn: true });
    const bar = await screen.findByRole("group", { name: "Selected bookmarks" });
    expect(bar).toHaveTextContent("0 of 3 selected");
    await user.click(within(bar).getByRole("checkbox", { name: "Select all shown (3)" }));
    expect(bar).toHaveTextContent("3 of 3 selected");
    await user.selectOptions(within(bar).getByLabelText("Add the selected to"), "c-1");
    await user.click(within(bar).getByRole("button", { name: "Add 3 to “Week 1”" }));

    const outcomes = await screen.findByRole("region", { name: /What happened: adding to “Week 1”/ });
    expect(within(outcomes).getByRole("status")).toHaveTextContent("2 added, 1 not available. 1 needs attention; the rest are done.");
    const lines = within(outcomes).getAllByRole("listitem").map((li) => li.textContent);
    expect(lines[0]).toMatch(/^Not available: A retired question/); // what needs attention comes first
    expect(lines.slice(1)).toEqual([expect.stringMatching(/^Added: What good patient assessment/), expect.stringMatching(/^Added: A time patient assessment/)]);
    await waitFor(() => expect(within(outcomes).getByRole("heading")).toHaveFocus());
    expect(bar).toHaveTextContent("1 of 3 selected"); // only the one that needs attention stays picked
    expect(screen.getByRole("checkbox", { name: "Select: A retired question" })).toBeChecked();
    expect(sent).toEqual([{ method: "POST", path: "/api/v1/me/collections/c-1/items/batch", body: { add: [
      { item_type: "question", track: "registered-nurse", ref_id: "e-good-0" },
      { item_type: "question", track: "registered-nurse", ref_id: "e-time-0" },
      { item_type: "question", track: "registered-nurse", ref_id: "gone-1" },
    ] } }]); // one request, nothing deleted
    expect(store.bookmarks).toHaveLength(3);
  });

  it("after a lost reply, sends the same ones again and reports what was already done", async () => {
    store.bookmarks = [mark("e-good-0", "What good patient assessment looks like"), mark("e-time-0", "A time patient assessment mattered")];
    store.collections = [collection("c-1", "Week 1")];
    let lose = true;
    server.use(http.post(`${API}/api/v1/me/collections/:id/items/batch`, async ({ request }) => {
      const body = (await request.clone().json()) as { add: { ref_id: string }[] };
      const c = store.collections[0]!;
      const results = body.add.map((ref) => {
        const key = `question:registered-nurse:${ref.ref_id}`;
        if (c.item_list.some((i) => i.ref_id === ref.ref_id)) return { key, outcome: "already_there", message: "Already in “Week 1”." };
        c.item_list.push({ ...collection("x", "x", [{ id: `i-${ref.ref_id}`, ref_id: ref.ref_id, title: ref.ref_id }]).item_list[0]!, position: c.item_list.length });
        return { key, outcome: "added", message: "Added to “Week 1”." };
      });
      if (lose) { lose = false; return HttpResponse.error(); } // it went through; the reply didn't
      return HttpResponse.json({ collection: { ...c, items: c.item_list.length }, results });
    }));
    const { user } = renderApp("/saved", { signedIn: true });
    const bar = await screen.findByRole("group", { name: "Selected bookmarks" });
    await user.click(within(bar).getByRole("checkbox", { name: "Select all shown (2)" }));
    await user.selectOptions(within(bar).getByLabelText("Add the selected to"), "c-1");
    await user.click(within(bar).getByRole("button", { name: "Add 2 to “Week 1”" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No reply came, so it isn't known which of these went through.");
    await user.click(within(alert).getByRole("button", { name: "Send again" }));
    const outcomes = await screen.findByRole("region", { name: /What happened/ });
    expect(within(outcomes).getByRole("status")).toHaveTextContent("2 already there. Nothing needs attention.");
    expect(store.collections[0]!.item_list).toHaveLength(2); // once each, not twice
  });

  it("drops a row that goes away from the selection, and takes at most 50 at a time", async () => {
    store.bookmarks = Array.from({ length: 51 }, (_, i) => mark(`q-${i}`, `Question ${i}`));
    store.collections = [collection("c-1", "Week 1")];
    const { user } = renderApp("/saved", { signedIn: true });
    const bar = await screen.findByRole("group", { name: "Selected bookmarks" });
    await user.click(within(bar).getByRole("checkbox", { name: "Select all shown (51)" }));
    await user.selectOptions(within(bar).getByLabelText("Add the selected to"), "c-1");
    expect(screen.getByText("Up to 50 at a time: 51 are selected.")).toBeInTheDocument();
    expect(within(bar).getByRole("button", { name: /Add 51/ })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Remove bookmark: Question 0" }));
    await waitFor(() => expect(bar).toHaveTextContent("50 of 50 selected")); // the removed one no longer counts
    expect(within(bar).getByRole("button", { name: "Add 50 to “Week 1”" })).toBeEnabled();
  });

  it("another account signing in on this browser starts with nothing selected, though its rows have the same keys", async () => {
    const bea = { ...user, id: "u-bea", email: "bea@example.com", display_name: "Bea" };
    server.use(http.post(`${API}/api/v1/auth/login`, () => HttpResponse.json(tokenResponse({ user: bea }))));
    store.bookmarks = [mark("e-good-0", "What good patient assessment looks like"), mark("e-time-0", "A time patient assessment mattered")];
    store.collections = [collection("c-1", "Week 1")];
    const app = renderApp("/saved", { signedIn: true });
    const bar = await screen.findByRole("group", { name: "Selected bookmarks" });
    await app.user.click(within(bar).getByRole("checkbox", { name: "Select all shown (2)" }));
    expect(bar).toHaveTextContent("2 of 2 selected");
    await app.user.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(app.router.state.location.pathname).not.toBe("/saved"));
    await act(() => app.router.navigate("/login"));
    await app.user.type(await screen.findByLabelText("Email"), bea.email);
    await app.user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await app.user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(app.router.state.location.pathname).not.toBe("/login"));
    await act(() => app.router.navigate("/saved"));
    // The same two questions, bookmarked by Bea: Ada's selection doesn't carry over to them.
    const beas = await screen.findByRole("group", { name: "Selected bookmarks" });
    expect(beas).toHaveTextContent("0 of 2 selected");
    expect(screen.getByRole("checkbox", { name: "Select: What good patient assessment looks like" })).not.toBeChecked();
  });
});

describe("Removing several items from a collection", () => {
  it("removes the chosen ones by keyboard, says each outcome, and leaves bookmarks alone", async () => {
    store.bookmarks = [mark("e-good-0", "What good patient assessment looks like")];
    store.collections = [collection("c-1", "Week 1", [
      { id: "i-1", ref_id: "e-good-0", title: "What good patient assessment looks like" },
      { id: "i-2", ref_id: "e-time-0", title: "A time patient assessment mattered" },
      { id: "i-3", ref_id: "m-pressure-0", title: "Patient assessment under pressure" },
    ])];
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    // By keyboard: Space on each row's checkbox.
    for (const name of ["Select: What good patient assessment looks like", "Select: A time patient assessment mattered"]) {
      const box = await screen.findByRole("checkbox", { name }, { timeout: 3000 });
      act(() => box.focus());
      await user.keyboard(" ");
      expect(box).toBeChecked();
    }
    const bar = screen.getByRole("group", { name: "Selected items" });
    expect(bar).toHaveTextContent("2 of 3 selected");
    expect(screen.getByText(/Removing only takes them out of this collection\. The questions stay in the library, and your bookmarks and answers aren't touched\./)).toBeInTheDocument();
    // Meanwhile another tab took the second one out already.
    store.collections[0]!.item_list = store.collections[0]!.item_list.filter((i) => i.id !== "i-2");
    await user.click(within(bar).getByRole("button", { name: "Remove 2 from “Week 1”" }));
    const outcomes = await screen.findByRole("region", { name: /What happened: removing from “Week 1”/ });
    expect(within(outcomes).getByRole("status")).toHaveTextContent("1 removed, 1 wasn't there. Nothing needs attention.");
    expect(within(outcomes).getByText(/Wasn't there/).closest("li")).toHaveTextContent("A time patient assessment mattered");
    await waitFor(() => expect(within(outcomes).getByRole("heading")).toHaveFocus()); // the rows that had focus are gone
    expect(screen.getAllByRole("checkbox", { name: /^Select: / })).toHaveLength(1);
    expect(sent.filter((s) => s.method !== "POST" || !s.path.endsWith("/batch"))).toEqual([]); // nothing else sent
    expect(store.bookmarks).toHaveLength(1); // the bookmark is still there
  });
});
