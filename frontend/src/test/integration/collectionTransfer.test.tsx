/**
 * Copy or move chosen items to another collection (Volume 17, prompt 6; docs/BULK_ACTIONS.md, "Copy or
 * move items"): the form's words before anything is sent (what the other collection already has, its
 * room, what arrives with each item, what leaves and what the queue will skip), the item's key as the
 * server names it, and the page: per-item outcomes, the selection kept only for what needs attention,
 * a lost reply sent again with the same items, and links to both collections.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Collection, CollectionItem } from "@/api/types";
import { itemKey, transferWords } from "@/features/saved/transfer";

import { resetExploreStore, store } from "../explore";
import { renderApp } from "../render";
import { API, server } from "../server";

const now = () => new Date().toISOString();
const item = (cid: string, i: number, extra: Partial<CollectionItem> = {}): CollectionItem => ({
  id: `${cid}-i${i}`, item_type: "question", track: "registered-nurse", ref_id: `q-${i}`, position: i, title: `Question ${i + 1}`,
  href: `/careers/registered-nurse/questions/q-${i}`, available: true, unavailable_reason: null, queue_done: false, practiced_since_added: false,
  ...extra,
});
const collection = (id: string, name: string, list: CollectionItem[], extra: Partial<Collection> = {}): Collection => ({
  id, name, items: list.length, queue_position: 0, queue_started: false, updated_at: now(), queue_done: list.filter((i) => i.queue_done).length,
  contains: null, item_list: list.map((x, n) => ({ ...x, position: n })), ...extra,
});

beforeEach(() => resetExploreStore());

describe("What the form says before anything is sent", () => {
  const source = collection("c-1", "Week 1", [item("c-1", 0, { queue_done: true }), item("c-1", 1), item("c-1", 2), item("c-1", 3)],
    { queue_started: true, queue_position: 1 });
  const chosen = [source.item_list[0]!, source.item_list[2]!];

  it("for a move: what the other already has and its room, what leaves, what the queue will skip, the mark left behind", () => {
    const dest = collection("c-2", "Week 2", [item("c-2", 2), ...Array.from({ length: 198 }, (_, n) => item("c-2", 100 + n))]);
    expect(transferWords({ source, chosen, dest, move: true, maxItems: 200 })).toEqual([
      "“Week 2” already has 1 of these 2: it won't be doubled.",
      "It has room for 1 more.",
      "Each goes at the end of “Week 2”, in this collection's order, at the version it was added at and with its “Mark reviewed”. A queue mark isn't carried.",
      "Leaves “Week 1”, each once it's in “Week 2”: “Question 1” and “Question 3”.",
      "Its queue (at item 2 of 4) will skip 1 not reached yet: “Question 3”.",
      "“Question 1” was marked done in this queue; that mark isn't carried to “Week 2”.",
    ]);
  });

  it("for a copy: the collection it's copied from doesn't change", () => {
    const dest = collection("c-2", "Week 2", []);
    const words = transferWords({ source, chosen, dest, move: false });
    expect(words[0]).toBe("“Week 2” has none of these 2 yet.");
    expect(words).toContain("“Week 1” doesn't change.");
    expect(words.join(" ")).toContain("Queue marks stay here.");
    expect(words.join(" ")).not.toMatch(/Leaves|skip/);
  });

  it("says how many won't fit, or that the other is full, and a queue not started yet", () => {
    const fresh = collection("c-1", "Week 1", [item("c-1", 0), item("c-1", 1), item("c-1", 2)]);
    const three = fresh.item_list;
    const nearly = collection("c-2", "Week 2", Array.from({ length: 199 }, (_, n) => item("c-2", 100 + n)));
    expect(transferWords({ source: fresh, chosen: three, dest: nearly, move: true, maxItems: 200 })).toEqual(expect.arrayContaining([
      "It has room for 1 more: 2 of these won't fit and will say so.",
      "This collection's queue hasn't started; it will hold 0 items.",
    ]));
    const full = collection("c-2", "Week 2", Array.from({ length: 200 }, (_, n) => item("c-2", 100 + n)));
    expect(transferWords({ source: fresh, chosen: three, dest: full, move: false, maxItems: 200 })).toContain(
      "It's full (200 of 200): none of the 3 new ones will fit, and each will say so.");
    // The room is the server's number as served; unread, it isn't stated (the server decides).
    expect(transferWords({ source: fresh, chosen: three, dest: nearly, move: false, maxItems: 201 })).toContain("It has room for 2 more: 1 of these won't fit and will say so.");
    expect(transferWords({ source: fresh, chosen: three, dest: nearly, move: false }).join(" ")).not.toMatch(/room|full|fit/);
  });

  it("names an item as the server does: a question's track, never a problem's", () => {
    expect(itemKey({ item_type: "question", track: "registered-nurse", ref_id: "q-1" })).toBe("question:registered-nurse:q-1");
    expect(itemKey({ item_type: "problem", track: "software-engineer", ref_id: "two-sum" })).toBe("problem::two-sum");
  });
});

/** Every transfer request the page sends, in order. */
function watchTransfers() {
  const bodies: unknown[] = [];
  server.events.on("request:start", ({ request }) => {
    if (request.url.endsWith("/items/transfer")) void request.clone().json().then((b) => bodies.push(b));
  });
  return bodies;
}

async function choose(user: ReturnType<typeof renderApp>["user"], titles: string[]) {
  for (const t of titles) await user.click(await screen.findByRole("checkbox", { name: `Select: ${t}` }));
}

describe("Copying and moving on a collection's page", () => {
  it("moves two through a lost reply: sent again with the same items, nothing done twice, both collections linked", async () => {
    store.collections = [
      collection("c-1", "Week 1", [item("c-1", 0), item("c-1", 1), item("c-1", 2)]),
      collection("c-2", "Week 2", [item("c-2", 7)]),
    ];
    store.loseTransferReply = true;
    const bodies = watchTransfers();
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    await choose(user, ["Question 1", "Question 3"]);
    await user.click(screen.getByRole("button", { name: "Move 2 to…" }));
    const form = screen.getByRole("form", { name: "Move 2 items to another collection" });
    expect(within(form).getByRole("button", { name: "Move 2" })).toBeDisabled(); // nothing chosen yet
    await user.selectOptions(within(form).getByLabelText("To collection"), "c-2");
    const words = await within(form).findByRole("list", { name: "Before you move them" });
    expect(words).toHaveTextContent("“Week 2” has none of these 2 yet.");
    expect(words).toHaveTextContent("It has room for 199 more.");
    expect(words).toHaveTextContent("Leaves “Week 1”, each once it's in “Week 2”: “Question 1” and “Question 3”.");
    await user.click(within(form).getByRole("button", { name: "Move 2 to “Week 2”" }));
    const lost = await screen.findByRole("alert");
    expect(lost).toHaveTextContent("Sending the same ones again is safe");
    await user.click(within(lost).getByRole("button", { name: "Send again" }));
    const outcomes = await screen.findByRole("region", { name: "What happened: moving to “Week 2”" });
    expect(within(outcomes).getByRole("status")).toHaveTextContent("2 already there. Nothing needs attention.");
    expect(screen.getByText(/This was sent again after no reply came/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "“Week 2”" })).toHaveAttribute("href", "/saved/collections/c-2");
    expect(screen.getByRole("link", { name: "“Week 1”" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText(/has 3 items, and/)).toHaveTextContent("Now: “Week 2” has 3 items, and “Week 1” has 1 item.");
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toEqual(bodies[0]); // the same items, named by what they are
    expect(bodies[0]).toEqual({ to: "c-2", move: true, items: [
      { item_type: "question", track: "registered-nurse", ref_id: "q-0" },
      { item_type: "question", track: "registered-nurse", ref_id: "q-2" },
    ] });
    expect(store.collections.find((c) => c.id === "c-2")!.item_list.map((i) => i.ref_id)).toEqual(["q-7", "q-0", "q-2"]);
    expect(screen.getAllByRole("checkbox", { name: /^Select: / }).map((b) => b.getAttribute("aria-label"))).toEqual(["Select: Question 2"]);
  });

  it("copies with an outcome for each: copied, already there, didn't fit; only what needs attention stays selected", async () => {
    store.collections = [
      collection("c-1", "Week 1", [item("c-1", 0), item("c-1", 1), item("c-1", 2)]),
      collection("c-2", "Week 2", [item("c-2", 1)]),
    ];
    store.itemLimit = 2;
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    await user.click(await screen.findByRole("checkbox", { name: "Select all shown (3)" }));
    await user.click(screen.getByRole("button", { name: "Copy 3 to…" }));
    const form = screen.getByRole("form", { name: "Copy 3 items to another collection" });
    await user.selectOptions(within(form).getByLabelText("To collection"), "c-2");
    expect(await within(form).findByText("“Week 2” already has 1 of these 3: it won't be doubled.")).toBeInTheDocument();
    expect(within(form).getByText("“Week 1” doesn't change.")).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "Copy 3 to “Week 2”" }));
    const outcomes = await screen.findByRole("region", { name: "What happened: copying to “Week 2”" });
    expect(within(outcomes).getByRole("status")).toHaveTextContent("1 copied, 1 already there, 1 didn't fit. 1 needs attention; the rest are done.");
    const rows = within(outcomes).getAllByRole("listitem").map((li) => li.textContent);
    expect(rows[0]).toBe("Didn't fit: Question 3 (“Week 2” holds up to 2 items.)"); // what needs attention first
    expect(rows).toContain("Copied: Question 1 (Copied to “Week 2”.)");
    expect(screen.getByRole("checkbox", { name: "Select: Question 3" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Select: Question 1" })).not.toBeChecked();
    expect(screen.getByText(/has 2 items, and/)).toHaveTextContent("“Week 1” has 3 items (unchanged).");
  });

  it("with no other collection, says so and sends nothing", async () => {
    store.collections = [collection("c-1", "Week 1", [item("c-1", 0)])];
    const bodies = watchTransfers();
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    await choose(user, ["Question 1"]);
    await user.click(screen.getByRole("button", { name: "Copy 1 to…" }));
    const form = screen.getByRole("form", { name: "Copy 1 item to another collection" });
    expect(await within(form).findByText(/You have no other collection yet\./)).toBeInTheDocument();
    expect(within(form).getByRole("link", { name: "Make one on Saved" })).toHaveAttribute("href", "/saved");
    expect(within(form).getByRole("button", { name: "Copy 1" })).toBeDisabled();
    expect(bodies).toEqual([]);
  });

  it("a refusal is said in the server's words and changes nothing on the page", async () => {
    store.collections = [collection("c-1", "Week 1", [item("c-1", 0)]), collection("c-2", "Week 2", [])];
    server.use(http.post(`${API}/api/v1/me/collections/:id/items/transfer`, () =>
      HttpResponse.json({ error: { code: "not_found", message: "Collection not found", details: null } }, { status: 404 })));
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    await choose(user, ["Question 1"]);
    await user.click(screen.getByRole("button", { name: "Move 1 to…" }));
    const form = screen.getByRole("form", { name: "Move 1 item to another collection" });
    await user.selectOptions(within(form).getByLabelText("To collection"), "c-2");
    await user.click(await within(form).findByRole("button", { name: "Move 1 to “Week 2”" }));
    expect(await screen.findByText("Collection not found")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /What happened/ })).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Select: Question 1" })).toBeChecked();
  });
});
