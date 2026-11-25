/**
 * Know the effects before you choose (Volume 12, prompt 9; docs/LIFECYCLE.md): deleting an
 * application and archiving a note show the server's plan first, every item by kind and title;
 * the button names the action and its reach; nothing is sent until it's pressed; a changed scope
 * shows the new plan and does nothing; a retry after a lost reply sends the same request key and
 * says it was already done; focus moves to the list and then to the outcome.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Application, Impact, LifecycleOutcome } from "@/api/types";

import { makeNote, noteStore } from "../notes";
import { renderApp } from "../render";
import { API, server } from "../server";

const now = () => new Date().toISOString();
const app: Application = {
  id: "a1", employer: "Mercy General", role_title: "Ward nurse", stage: "interviewing", applied_on: "2026-10-30", next_action: "", next_action_due: null,
  target: null, archived: false, next_event: null, updated_at: now(), link: null, notes: "", notes_revision: 1, stories: [], events: [], history: [], created_at: now(),
};
const fx = (effect: Impact["effects"][number]["effect"], kind: string, title: string, id: string, note: string | null = null) => ({ effect, kind, title, id, note });
const impact = (over: Partial<Impact> = {}): Impact => ({
  action: "delete_application", target_id: "a1", title: "Ward nurse at Mercy General",
  summary: "Delete this application, its 2 events and 1 kit",
  effects: [
    fx("deleted", "application", "Ward nurse at Mercy General", "a1", "With its notes."),
    fx("deleted", "interview event", "Phone screen (3 November 2026)", "e1"),
    fx("deleted", "interview event", "Panel interview (12 November 2026)", "e2"),
    fx("deleted", "interview-day kit", "Kit for Panel interview", "e2", "Its checklist, questions and chosen examples, and what it kept from them."),
    fx("unlinked", "story", "Two call lights", "s1", "Stays in your story bank."),
    fx("unavailable", "schedule entry", "Prepare: Panel interview (Mercy General)", "sch1", "Stays on your schedule, marked no longer available."),
    fx("kept", "note", "References for Mercy", "n1", "Made from a reflection's next step; it stays."),
  ],
  notes: ["This can't be undone. Archive keeps it out of the way instead.", "Backups you made before now still hold a copy until you delete them."],
  fingerprint: "fp-1-aaaaaaaaaaaaaaaa", ...over,
});
const outcome = (i: Impact, over: Partial<LifecycleOutcome> = {}): LifecycleOutcome => ({
  ...i, done_at: now(), replayed: false, message: "Deleted Ward nurse at Mercy General.", ...over,
});

let writes: { path: string; body: Record<string, unknown> }[] = [];
function serve(post: (body: Record<string, unknown>, n: number) => Response | Promise<Response>, preview: () => Impact = () => impact()) {
  writes = [];
  server.use(
    http.get(`${API}/api/v1/me/applications/a1`, () => HttpResponse.json(app)),
    http.get(`${API}/api/v1/me/applications/a1/delete-preview`, () => HttpResponse.json(preview())),
    http.get(`${API}/api/v1/me/applications`, () => HttpResponse.json([])),
    http.post(`${API}/api/v1/me/applications/a1/delete`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      writes.push({ path: "delete", body });
      return post(body, writes.length);
    }),
    http.delete(`${API}/api/v1/me/applications/a1`, () => { writes.push({ path: "DELETE", body: {} }); return new HttpResponse(null, { status: 204 }); }),
  );
}

describe("Deleting an application shows what it reaches first", () => {
  it("lists every item by what happens to it, sends nothing until asked, and lands focus on the outcome", async () => {
    serve(() => HttpResponse.json(outcome(impact())));
    const { user } = renderApp("/applications/a1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Delete…" }, { timeout: 3000 }));
    const group = await screen.findByRole("group", { name: "What this will do" });
    await waitFor(() => expect(within(group).getByRole("heading", { name: "What this will do" })).toHaveFocus());
    expect(within(group).getByRole("heading", { name: "Deleted (4)" })).toBeInTheDocument();
    expect(within(group).getByRole("heading", { name: "Unlinked (the other record stays) (1)" })).toBeInTheDocument();
    expect(within(group).getByRole("heading", { name: "Kept, but no longer available (1)" })).toBeInTheDocument();
    expect(within(group).getByRole("heading", { name: "Kept (1)" })).toBeInTheDocument();
    expect(group).toHaveTextContent("Interview-day kit: Kit for Panel interview");
    expect(group).toHaveTextContent("Schedule entry: Prepare: Panel interview (Mercy General) Stays on your schedule, marked no longer available.");
    expect(group).toHaveTextContent("Note: References for Mercy Made from a reflection's next step; it stays.");
    expect(group).toHaveTextContent("This can't be undone. Archive keeps it out of the way instead.");
    expect(group).toHaveTextContent("Backups you made before now still hold a copy until you delete them.");
    expect(writes).toEqual([]); // previewing sends nothing

    await user.click(within(group).getByRole("button", { name: "Delete this application, its 2 events and 1 kit" }));
    const done = await screen.findByRole("status");
    expect(done).toHaveTextContent("Deleted Ward nurse at Mercy General. With it went its 2 events and 1 kit. Everything listed as kept or unlinked is where it was.");
    await waitFor(() => expect(done).toHaveFocus());
    expect(screen.getByRole("heading", { level: 1, name: "Your applications" })).toBeInTheDocument();
    expect(writes).toHaveLength(1);
    expect(writes[0]!.body.expected_fingerprint).toBe("fp-1-aaaaaaaaaaaaaaaa");
    expect(typeof writes[0]!.body.client_request_id).toBe("string");
  });

  it("Cancel sends nothing and closes the list", async () => {
    serve(() => HttpResponse.json(outcome(impact())));
    const { user } = renderApp("/applications/a1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Delete…" }, { timeout: 3000 }));
    const group = await screen.findByRole("group", { name: "What this will do" });
    await user.click(within(group).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("group", { name: "What this will do" })).not.toBeInTheDocument();
    expect(writes).toEqual([]);
  });

  it("a scope that changed meanwhile shows the new list and does nothing until asked again", async () => {
    const wider = impact({
      summary: "Delete this application, its 3 events and 1 kit",
      effects: [...impact().effects, fx("deleted", "interview event", "Final interview (15 January 2030)", "e3")],
      fingerprint: "fp-2-bbbbbbbbbbbbbbbb",
    });
    serve((body) => body.expected_fingerprint === wider.fingerprint
      ? HttpResponse.json(outcome(wider))
      : HttpResponse.json({ error: { code: "impact_changed", message: "What this would affect has changed since you looked.", request_id: "r", details: { current: wider } } }, { status: 409 }));
    const { user } = renderApp("/applications/a1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Delete…" }, { timeout: 3000 }));
    const group = await screen.findByRole("group", { name: "What this will do" });
    await user.click(within(group).getByRole("button", { name: "Delete this application, its 2 events and 1 kit" }));
    expect(await within(group).findByText("What this affects changed since you looked. Nothing was done: check the list again.")).toBeInTheDocument();
    expect(group).toHaveTextContent("Interview event: Final interview (15 January 2030)");
    expect(within(group).getByRole("heading", { name: "Deleted (5)" })).toBeInTheDocument();
    await waitFor(() => expect(within(group).getByRole("heading", { name: "What this will do" })).toHaveFocus());
    expect(screen.getByRole("heading", { level: 1, name: "Ward nurse" })).toBeInTheDocument(); // still here
    await user.click(within(group).getByRole("button", { name: "Delete this application, its 3 events and 1 kit" }));
    expect(await screen.findByRole("status")).toHaveTextContent("With it went its 3 events and 1 kit.");
    expect(writes.map((w) => w.body.expected_fingerprint)).toEqual(["fp-1-aaaaaaaaaaaaaaaa", "fp-2-bbbbbbbbbbbbbbbb"]);
    expect(writes[0]!.body.client_request_id).not.toBe(writes[1]!.body.client_request_id); // a different request
  });

  it("a retry after a lost reply sends the same request and says it was already done", async () => {
    serve((_, n) => n === 1
      ? HttpResponse.error()
      : HttpResponse.json(outcome(impact(), { replayed: true, message: "This was already done; nothing was done again." })));
    const { user } = renderApp("/applications/a1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Delete…" }, { timeout: 3000 }));
    const group = await screen.findByRole("group", { name: "What this will do" });
    const go = within(group).getByRole("button", { name: "Delete this application, its 2 events and 1 kit" });
    await user.click(go);
    expect(await within(group).findByRole("alert")).toBeInTheDocument();
    await user.click(go);
    const done = await screen.findByRole("status");
    expect(done).toHaveTextContent("This was already done; nothing was done again.");
    expect(done).not.toHaveTextContent("With it went");
    expect(writes).toHaveLength(2);
    expect(writes[1]!.body.client_request_id).toBe(writes[0]!.body.client_request_id);
    expect(writes.some((w) => w.path === "DELETE")).toBe(false);
  });
});

describe("Archiving a note shows what it does first", () => {
  it("says it hides and unpins, erases nothing, and focuses the outcome", async () => {
    const note = makeNote({ title: "Handover phrases", body: "SBAR first.", pinned: true });
    noteStore.notes.push(note);
    const preview: Impact = {
      action: "archive_note", target_id: note.id, title: "Handover phrases", summary: "Archive this note",
      effects: [
        fx("archived", "note", "Handover phrases", note.id, "Hidden from your notes list, Continue and search unless you include archived notes. Unarchive it any time; nothing is erased."),
        fx("unlinked", "pin", "Pinned to the top of your notes", note.id, "Unarchiving won't pin it again."),
      ],
      notes: ["Archiving isn't deleting: the note stays in your data export and can still go in a practice packet."],
      fingerprint: "fp-note-cccccccccccc",
    };
    const sent: Record<string, unknown>[] = [];
    server.use(
      http.get(`${API}/api/v1/me/notes/${note.id}/archive-preview`, () => HttpResponse.json(preview)),
      http.post(`${API}/api/v1/me/notes/${note.id}/archive`, async ({ request }) => {
        sent.push((await request.json()) as Record<string, unknown>);
        Object.assign(noteStore.notes[0]!, { archived: true, pinned: false });
        return HttpResponse.json({ ...preview, done_at: now(), replayed: false, message: "Archived Handover phrases." });
      }),
    );
    const { user } = renderApp(`/notes/${note.id}`, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Archive…" }, { timeout: 3000 }));
    const group = await screen.findByRole("group", { name: "What this will do" });
    expect(within(group).getByRole("heading", { name: "Archived (you can undo this) (1)" })).toBeInTheDocument();
    expect(group).toHaveTextContent("Pin: Pinned to the top of your notes Unarchiving won't pin it again.");
    expect(group).toHaveTextContent("Archiving isn't deleting");
    expect(group).not.toHaveTextContent(/permanent|erased for good/i);
    expect(sent).toEqual([]);
    await user.click(within(group).getByRole("button", { name: "Archive this note" }));
    const done = await screen.findByRole("status");
    expect(done).toHaveTextContent("Archived Handover phrases. It's hidden from your notes list, Continue and search; nothing is erased. Unarchive brings it back.");
    await waitFor(() => expect(done).toHaveFocus());
    expect(await screen.findByRole("button", { name: "Unarchive" })).toBeInTheDocument();
    expect(sent).toEqual([{ expected_fingerprint: "fp-note-cccccccccccc", client_request_id: expect.any(String) }]);
  });
});
