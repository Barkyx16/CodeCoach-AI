/**
 * Marking several saved items reviewed at once (Volume 15, prompt 6; docs/BULK_ACTIONS.md): on the
 * saved list and in a collection, the selected rows are sent in one request, each at the version its
 * row shows, and the page says what happened to each, with the ones that still ask kept selected.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Bookmark, Collection, NoteFreshness, ReviewResult } from "@/api/types";

import { resetExploreStore, store } from "../explore";
import { renderApp } from "../render";
import { API, server } from "../server";

const now = () => new Date().toISOString();
const changed = (current = 2): NoteFreshness => ({
  state: "needs_review", kind: "question", captured_version: 1, reviewed_version: null, current_version: current,
  text: `The question changed since you saved this item (version 1, now ${current}). Review whether it's still what you saved it for.`,
  changes: [], change_notes: [], comparable: true, reviews: [],
});
const reviewed = (): NoteFreshness => ({ ...changed(), state: "current", reviewed_version: 2, text: "You marked it reviewed at version 2 on 15 November 2026." });
const mark = (ref_id: string, title: string, freshness: NoteFreshness | null, item_type: "question" | "drill" = "question"): Bookmark => ({
  id: `b-${ref_id}`, item_type, track: item_type === "question" ? "registered-nurse" : "", ref_id, title, href: null,
  available: true, unavailable_reason: null, content_version: item_type === "question" ? 1 : null, freshness, created_at: now(),
});

let sent: { path: string; body: unknown }[] = [];
beforeEach(() => {
  resetExploreStore();
  sent = [];
});

describe("Marking several saved items reviewed", () => {
  it("sends each at the version shown and says what happened to each", async () => {
    store.bookmarks = [mark("m-pressure-0", "Under pressure", changed()), mark("e-good-0", "A good nurse", changed(3)), mark("example", "Drill: an example", null, "drill")];
    server.use(http.post(`${API}/api/v1/me/bookmarks/review/batch`, async ({ request }) => {
      const body = (await request.json()) as { items: { ref_id: string; reviewed_version: number }[] };
      sent.push({ path: "/api/v1/me/bookmarks/review/batch", body });
      store.bookmarks = store.bookmarks.map((b) => (b.ref_id === "m-pressure-0" ? { ...b, freshness: reviewed() } : b));
      const results: ReviewResult[] = [
        { key: "question:registered-nurse:m-pressure-0", outcome: "reviewed", message: "Marked reviewed at version 2." },
        { key: "question:registered-nurse:e-good-0", outcome: "newer_since", message: "Marked reviewed at version 3; it's version 4 now, so it still asks." },
        { key: "drill::example", outcome: "not_versioned", message: "A drill has no versions to review." },
      ];
      return HttpResponse.json({ bookmarks: store.bookmarks, results });
    }));
    const { user } = renderApp("/saved", { signedIn: true });
    const bar = await screen.findByRole("group", { name: "Selected bookmarks" });
    await user.click(within(bar).getByRole("checkbox", { name: "Select all shown (3)" }));
    await user.click(within(bar).getByRole("button", { name: "Mark 3 reviewed" }));

    const outcomes = await screen.findByRole("region", { name: "What happened: marking reviewed" });
    expect(within(outcomes).getByRole("status")).toHaveTextContent(
      "1 marked reviewed, 1 still asks: a newer version, 1 no versions to review. 1 needs attention; the rest are done.",
    );
    const lines = within(outcomes).getAllByRole("listitem").map((li) => li.textContent);
    expect(lines[0]).toMatch(/^Still asks: a newer version: A good nurse \(Marked reviewed at version 3; it's version 4 now/);
    await waitFor(() => expect(within(outcomes).getByRole("heading")).toHaveFocus());
    expect(bar).toHaveTextContent("1 of 3 selected"); // the one that still asks stays picked
    expect(sent).toEqual([{ path: "/api/v1/me/bookmarks/review/batch", body: { items: [
      { item_type: "question", track: "registered-nurse", ref_id: "m-pressure-0", reviewed_version: 2 },
      { item_type: "question", track: "registered-nurse", ref_id: "e-good-0", reviewed_version: 3 },
      { item_type: "drill", track: "", ref_id: "example", reviewed_version: 1 },
    ] } }]);
    // The reviewed one no longer asks; the rows are all still there.
    const row = screen.getByRole("checkbox", { name: "Select: Under pressure" }).closest("li") as HTMLElement;
    await waitFor(() => expect(row).not.toHaveTextContent("changed since you saved"));
    expect(within(screen.getByRole("checkbox", { name: "Select: A good nurse" }).closest("li") as HTMLElement).getByText(/changed since you saved/)).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox", { name: /^Select: / })).toHaveLength(3);
  });

  it("marks several items of a collection reviewed, leaving them where they are", async () => {
    const c: Collection = {
      id: "c-1", name: "Week 1", items: 2, queue_position: 0, queue_started: true, updated_at: now(), queue_done: 0, contains: null,
      item_list: [
        { id: "i-1", item_type: "question", track: "registered-nurse", ref_id: "m-pressure-0", position: 0, title: "Under pressure", href: null,
          available: true, unavailable_reason: null, queue_done: false, practiced_since_added: false, content_version: 1, freshness: changed() },
        { id: "i-2", item_type: "question", track: "registered-nurse", ref_id: "e-good-0", position: 1, title: "A good nurse", href: null,
          available: true, unavailable_reason: null, queue_done: false, practiced_since_added: false, content_version: 2, freshness: reviewed() },
      ],
    };
    store.collections = [c];
    server.use(http.post(`${API}/api/v1/me/collections/c-1/items/review/batch`, async ({ request }) => {
      sent.push({ path: "/api/v1/me/collections/c-1/items/review/batch", body: await request.json() });
      const after = { ...c, item_list: c.item_list.map((i) => ({ ...i, freshness: reviewed() })) };
      const results: ReviewResult[] = [
        { key: "i-1", outcome: "reviewed", message: "Marked reviewed at version 2." },
        { key: "i-2", outcome: "already_reviewed", message: "Already reviewed at version 2; nothing more recorded." },
      ];
      return HttpResponse.json({ collection: after, results });
    }));
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    const bar = await screen.findByRole("group", { name: "Selected items" });
    await user.click(within(bar).getByRole("checkbox", { name: "Select all shown (2)" }));
    await user.click(within(bar).getByRole("button", { name: "Mark 2 reviewed" }));
    const outcomes = await screen.findByRole("region", { name: "What happened: marking reviewed in “Week 1”" });
    expect(within(outcomes).getByRole("status")).toHaveTextContent("1 marked reviewed, 1 already reviewed. Nothing needs attention.");
    expect(sent).toEqual([{ path: "/api/v1/me/collections/c-1/items/review/batch", body: { items: [
      { item_id: "i-1", reviewed_version: 2 }, { item_id: "i-2", reviewed_version: 2 },
    ] } }]);
    expect(bar).toHaveTextContent("0 of 2 selected");
    const order = within(screen.getByRole("list", { name: "Items in order" })).getAllByRole("listitem");
    expect(order[0]).toHaveTextContent("Under pressure");
  });
});
