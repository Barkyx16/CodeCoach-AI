/**
 * Saved items that know their version (Volume 14, prompt 7; docs/STORY_FRESHNESS.md, "Saved items
 * and collections"): the saved list, a collection and its practice queue badge an item whose source
 * has a newer version that matters, show what changed, and "Mark reviewed" sends the version shown
 * and clears the badge; the saved list filters by it. The item itself is never changed, moved or
 * unsaved: nothing else is sent.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Bookmark, Collection, NoteFreshness } from "@/api/types";

import { resetExploreStore, store } from "../explore";
import { renderApp } from "../render";
import { API, server } from "../server";

const now = () => new Date().toISOString();
const updated = (): NoteFreshness => ({
  state: "needs_review", kind: "question", captured_version: 1, reviewed_version: null, current_version: 2,
  text: "The question changed since you saved this item (version 1, now 2). Review whether it's still what you saved it for.",
  changes: [{ field: "Question", before: "Tell me about a time you worked under pressure.", after: "Describe a shift when the pressure was on." }],
  change_notes: ["Version 2: Clearer about patient safety."], comparable: true, reviews: [],
});
const current = (reviewed: number | null = null): NoteFreshness => ({
  state: "current", kind: "question", captured_version: 1, reviewed_version: reviewed, current_version: 2,
  text: reviewed ? "You marked it reviewed at version 2 on 15 November 2026." : "Up to date with the question (version 2).",
  changes: [], change_notes: [], comparable: true, reviews: [],
});
const mark = (ref_id: string, title: string, freshness: NoteFreshness | null): Bookmark => ({
  id: `b-${ref_id}`, item_type: "question", track: "registered-nurse", ref_id, title, href: `/careers/registered-nurse/questions/${ref_id}`,
  available: true, unavailable_reason: null, content_version: 1, freshness, created_at: now(),
});
const collection = (freshness: NoteFreshness): Collection => ({
  id: "c-1", name: "Week 1", items: 2, queue_position: 0, queue_started: true, updated_at: now(), queue_done: 0, contains: null,
  item_list: [
    { id: "i-1", item_type: "question", track: "registered-nurse", ref_id: "m-pressure-0", position: 0, title: "Under pressure",
      href: "/careers/registered-nurse/questions/m-pressure-0", available: true, unavailable_reason: null, queue_done: false,
      practiced_since_added: false, content_version: 1, freshness },
    { id: "i-2", item_type: "question", track: "registered-nurse", ref_id: "e-good-0", position: 1, title: "A good nurse",
      href: "/careers/registered-nurse/questions/e-good-0", available: true, unavailable_reason: null, queue_done: false,
      practiced_since_added: false, content_version: 2, freshness: current() },
  ],
});

let sent: { path: string; body: unknown }[] = [];
beforeEach(() => {
  resetExploreStore();
  sent = [];
  server.events.removeAllListeners();
  server.events.on("request:start", async ({ request }) => {
    if (request.method === "GET" || request.url.endsWith("/auth/refresh")) return;
    sent.push({ path: new URL(request.url).pathname, body: await request.clone().json().catch(() => null) });
  });
});
afterEach(() => { server.events.removeAllListeners(); });

describe("Saved items whose source changed", () => {
  it("badges the saved item, shows what changed, and Mark reviewed sends the version shown", async () => {
    store.bookmarks = [mark("m-pressure-0", "Under pressure", updated()), mark("e-good-0", "A good nurse", current())];
    server.use(http.post(`${API}/api/v1/me/bookmarks/review`, async ({ request }) => {
      const body = (await request.json()) as { ref_id: string };
      return HttpResponse.json(mark(body.ref_id, "Under pressure", current(2)));
    }));
    const { user } = renderApp("/saved", { signedIn: true });
    const row = (await screen.findByRole("link", { name: "Under pressure" }, { timeout: 3000 })).closest("li")!;
    expect(within(row).getByText("Source updated")).toBeInTheDocument();
    expect(row).toHaveTextContent("saved just now at version 1");
    const other = screen.getByRole("link", { name: "A good nurse" }).closest("li")!;
    expect(within(other).queryByText("Source updated")).toBeNull(); // up to date: nothing to say

    await user.click(within(row).getByText("What changed"));
    expect(row).toHaveTextContent("The question changed since you saved this item (version 1, now 2).");
    expect(row).toHaveTextContent("Tell me about a time you worked under pressure.");
    expect(row).toHaveTextContent("Describe a shift when the pressure was on.");
    expect(row).toHaveTextContent("Version 2: Clearer about patient safety.");
    await user.click(within(row).getByRole("button", { name: "Mark reviewed (version 2): Under pressure" }));
    expect(await screen.findByText("Marked reviewed at version 2. Nothing about the saved item changed.", undefined, { timeout: 3000 })).toBeInTheDocument();
    await waitFor(() => expect(within(row).queryByText("Source updated")).toBeNull());
    expect(sent).toEqual([{ path: "/api/v1/me/bookmarks/review", body: { item_type: "question", track: "registered-nurse", ref_id: "m-pressure-0", reviewed_version: 2 } }]);
    expect(screen.getByRole("link", { name: "Under pressure" })).toBeInTheDocument(); // still saved, still there
  });

  it("filters the saved list to the items whose source was updated", async () => {
    store.bookmarks = [mark("m-pressure-0", "Under pressure", updated()), mark("e-good-0", "A good nurse", current())];
    const { user, router } = renderApp("/saved", { signedIn: true });
    await user.click(await screen.findByRole("checkbox", { name: "Source updated (1)" }, { timeout: 3000 }));
    expect(router.state.location.search).toBe("?updated=1");
    expect(screen.getByRole("link", { name: "Under pressure" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "A good nurse" })).toBeNull();
    expect(screen.getByRole("checkbox", { name: "Select all shown (1)" })).toBeInTheDocument(); // bulk actions see only these
    // Reviewed while filtered: it stays in view with what it says, until the filter changes.
    server.use(http.post(`${API}/api/v1/me/bookmarks/review`, () => HttpResponse.json(mark("m-pressure-0", "Under pressure", current(2)))));
    const row = screen.getByRole("link", { name: "Under pressure" }).closest("li")!;
    await user.click(within(row).getByText("What changed"));
    await user.click(within(row).getByRole("button", { name: "Mark reviewed (version 2): Under pressure" }));
    expect(await screen.findByText("Marked reviewed at version 2. Nothing about the saved item changed.", undefined, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Under pressure" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Source updated (0)" })).toBeChecked();
    await user.click(screen.getByRole("checkbox", { name: "Source updated (0)" }));
    expect(screen.getByRole("link", { name: "A good nurse" })).toBeInTheDocument();
  });

  it("says when nothing has a source update, and an item saved before versions reads not known", async () => {
    const unknown: NoteFreshness = { ...current(), state: "unknown", captured_version: null, text: "Whether the question changed since isn't known: this item was saved before versions were recorded." };
    store.bookmarks = [mark("e-good-0", "A good nurse", unknown)];
    const { user } = renderApp("/saved?updated=1", { signedIn: true });
    expect(await screen.findByText("None of your saved items has a source update to review.", undefined, { timeout: 3000 })).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Source updated (0)" }));
    const row = (await screen.findByRole("link", { name: "A good nurse" })).closest("li")!;
    expect(within(row).getByText("Version not known")).toBeInTheDocument();
    expect(within(row).queryByText("Source updated")).toBeNull(); // never "up to date", never "updated"
  });
});

describe("A collection and its queue", () => {
  it("badges the item in the collection and reviews it there, where it stays", async () => {
    let c = collection(updated());
    server.use(
      http.get(`${API}/api/v1/me/collections/c-1`, () => HttpResponse.json(c)),
      http.post(`${API}/api/v1/me/collections/c-1/items/i-1/review`, () => {
        c = collection(current(2));
        return HttpResponse.json(c);
      }),
    );
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    const row = (await screen.findByRole("link", { name: "Under pressure" }, { timeout: 3000 })).closest("li")!;
    expect(within(row).getByText("Source updated")).toBeInTheDocument();
    await user.click(within(row).getByText("What changed"));
    await user.click(within(row).getByRole("button", { name: "Mark reviewed (version 2): Under pressure" }));
    await waitFor(() => expect(within(screen.getByRole("link", { name: "Under pressure" }).closest("li")!).queryByText("Source updated")).toBeNull());
    expect(sent).toEqual([{ path: "/api/v1/me/collections/c-1/items/i-1/review", body: { reviewed_version: 2 } }]);
    expect(screen.getAllByRole("listitem").filter((li) => li.classList.contains("collection-item")).map((li) => li.textContent?.slice(0, 20)))
      .toEqual([expect.stringContaining("Under pressure"), expect.stringContaining("A good nurse")]); // same order
  });

  it("the practice queue shows the same badge for the current item and in its list", async () => {
    server.use(http.get(`${API}/api/v1/me/collections/c-1`, () => HttpResponse.json(collection(updated()))));
    renderApp("/saved/collections/c-1/practice", { signedIn: true });
    const now = await screen.findByRole("heading", { name: "Under pressure" }, { timeout: 3000 });
    expect(within(now.closest(".queue-current") as HTMLElement).getByText("Source updated")).toBeInTheDocument();
    const list = screen.getByRole("region", { name: "Everything in this queue" });
    expect(list).toHaveTextContent("1. Under pressureTo do · Source updated");
    expect(list).not.toHaveTextContent("2. A good nurseTo do · Source updated");
  });
});
