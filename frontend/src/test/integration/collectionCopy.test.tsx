/**
 * Duplicate a collection (Volume 16, prompt 8; docs/BULK_ACTIONS.md): the form says what the copy
 * keeps and that the queue starts fresh; the limit is said before it's reached and the button is off
 * at it; a lost reply is sent again with the same key, so the server makes one copy; the copy's page
 * says it's a copy and of which collection; a name already used is refused with the server's words.
 */
import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Collection } from "@/api/types";

import { resetExploreStore, store } from "../explore";
import { renderApp } from "../render";
import { API, server } from "../server";

const now = () => new Date().toISOString();
const collection = (id: string, name: string, n = 2, extra: Partial<Collection> = {}): Collection => ({
  id, name, items: n, queue_position: 0, queue_started: false, updated_at: now(), queue_done: 0, contains: null,
  item_list: Array.from({ length: n }, (_, i) => ({
    id: `${id}-i${i}`, item_type: "question" as const, track: "registered-nurse", ref_id: `q-${i}`, position: i, title: `Question ${i + 1}`,
    href: `/careers/registered-nurse/questions/q-${i}`, available: true, unavailable_reason: null, queue_done: false, practiced_since_added: false,
  })),
  ...extra,
});

beforeEach(() => resetExploreStore());

/** The server's duplicate: one copy per key; the first reply can be lost. */
function serveDuplicate({ loseFirst = false, clash = false } = {}) {
  const keys = new Map<string, string>();
  const bodies: { name: string | null; client_request_id: string }[] = [];
  let lost = loseFirst;
  server.use(http.post(`${API}/api/v1/me/collections/:id/duplicate`, async ({ params, request }) => {
    const body = (await request.json()) as { name: string | null; client_request_id: string };
    bodies.push(body);
    if (clash) {
      return HttpResponse.json({ error: { code: "name_taken", message: `You already have a collection called “${body.name}” (names are compared in any letter case). Choose another name.`, details: null } }, { status: 409 });
    }
    const src = store.collections.find((c) => c.id === params.id)!;
    let copyId = keys.get(body.client_request_id);
    if (!copyId) {
      copyId = `copy-${keys.size + 1}`;
      keys.set(body.client_request_id, copyId);
      store.collections.unshift(collection(copyId, body.name ?? `${src.name} (copy)`, src.items, { copied_from_id: src.id }));
    }
    if (lost) { lost = false; return HttpResponse.error(); } // made, but the reply never arrives
    return HttpResponse.json(store.collections.find((c) => c.id === copyId), { status: 201 });
  }));
  return { bodies, keys };
}

describe("Duplicating a collection", () => {
  it("says what the copy keeps, survives a lost reply with one copy, and the copy says whose it is", async () => {
    store.collections = [collection("c-1", "Week 1")];
    const { bodies, keys } = serveDuplicate({ loseFirst: true });
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Duplicate" }));
    const form = screen.getByRole("form", { name: "Duplicate “Week 1”" });
    expect(form).toHaveTextContent("each at the version it was added at and with its “Mark reviewed”");
    expect(form).toHaveTextContent("Its queue starts at the beginning, and this collection doesn't change.");
    expect(within(form).getByLabelText("Name for the copy")).toHaveAttribute("placeholder", "Week 1 (copy)");
    await user.click(within(form).getByRole("button", { name: "Make the copy" }));
    const lost = await within(form).findByRole("alert");
    expect(lost).toHaveTextContent("Sending it again is safe: it makes one copy, not two.");
    await user.click(within(lost).getByRole("button", { name: "Send again" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Week 1 (copy)" })).toBeInTheDocument();
    expect(screen.getByText(/Made “Week 1 \(copy\)”: the same items in the same order/)).toBeInTheDocument();
    expect(screen.getByText(/A copy of/)).toHaveTextContent("A copy of “Week 1”. Its queue and its “Mark reviewed” are its own");
    expect(screen.getByRole("link", { name: "“Week 1”" })).toHaveAttribute("href", "/saved/collections/c-1");
    // Both sends carried the same key: the server made one copy.
    expect(bodies).toHaveLength(2);
    expect(bodies[0]!.client_request_id).toBe(bodies[1]!.client_request_id);
    expect(keys.size).toBe(1);
    expect(store.collections.map((c) => c.name)).toEqual(["Week 1 (copy)", "Week 1"]);
  });

  it("says the limit before it's reached and won't send at it", async () => {
    store.collections = [collection("c-1", "Week 1"), ...Array.from({ length: 49 }, (_, i) => collection(`c-x${i}`, `Other ${i}`, 0))];
    const { bodies } = serveDuplicate();
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Duplicate" }));
    const form = screen.getByRole("form", { name: "Duplicate “Week 1”" });
    expect(await within(form).findByRole("status")).toHaveTextContent("You have 50 of 50 collections: delete one to make room for a copy.");
    expect(within(form).getByRole("button", { name: "Make the copy" })).toBeDisabled();
    expect(bodies).toEqual([]);
  });

  it("near the limit says how many there would be; a name already used is refused in the server's words", async () => {
    store.collections = [collection("c-1", "Week 1"), ...Array.from({ length: 46 }, (_, i) => collection(`c-x${i}`, `Other ${i}`, 0))];
    serveDuplicate({ clash: true });
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Duplicate" }));
    const form = screen.getByRole("form", { name: "Duplicate “Week 1”" });
    expect(await within(form).findByText("You have 47 of 50 collections; the copy would make 48.")).toBeInTheDocument();
    await user.type(within(form).getByLabelText("Name for the copy"), "Other 3");
    await user.click(within(form).getByRole("button", { name: "Make the copy" }));
    expect(await within(form).findByText(/You already have a collection called “Other 3”/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Week 1" })).toBeInTheDocument(); // still here
  });
});
