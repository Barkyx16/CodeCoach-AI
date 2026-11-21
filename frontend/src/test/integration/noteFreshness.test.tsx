import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Note, NoteFreshness } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { makeNote, noteStore } from "../notes";
import { renderApp } from "../render";
import { API, server } from "../server";

/** A note knows where it came from (Volume 13, prompt 6; docs/STORY_FRESHNESS.md, "Notes"). */

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const SOURCE = { type: "question" as const, id: "m-pressure-0", track: "registered-nurse", version: "1", title: "Working under pressure", href: "/careers/registered-nurse/questions/m-pressure-0", available: true, career_title: "Registered Nurse" };

const fresh = (over: Partial<NoteFreshness>): NoteFreshness => ({
  state: "needs_review", kind: "question", captured_version: 1, reviewed_version: null, current_version: 2,
  text: "The question changed since you captured this note (version 1, now 2). Review whether your note still fits.",
  changes: [{ field: "Question", before: "Tell me about a time you worked under pressure.", after: "Describe a shift when the pressure was on and you kept patients safe." }],
  change_notes: ["Version 2: Clearer about patient safety."], comparable: true, reviews: [], ...over,
});

function seed(freshness: NoteFreshness): Note {
  const n = makeNote({
    title: "Staying calm", body: "Name the risk first.", source: SOURCE, excerpt: "Tell me about a time you worked under pressure.",
    excerpt_kind: "quote", freshness, source_updated: freshness.state === "needs_review",
  });
  noteStore.notes.push(n);
  return n;
}

function serveReview(reply: (version: number) => NoteFreshness) {
  const sent: unknown[] = [];
  server.use(http.post(`${API}/api/v1/me/notes/:id/source-review`, async ({ request }) => {
    const body = (await request.json()) as { reviewed_version: number };
    sent.push(body);
    return HttpResponse.json(reply(body.reviewed_version));
  }));
  return sent;
}

describe("A note's changed source", () => {
  it("is said above the snapshot, side by side, and Mark reviewed records the version shown without touching the note", async () => {
    asNurse();
    const n = seed(fresh({}));
    const sent = serveReview((v) => fresh({ state: "current", reviewed_version: v, text: `You marked it reviewed at version ${v} on 15 November.`, changes: [], change_notes: [] }));
    const { user } = renderApp(`/notes/${n.id}`, { signedIn: true });
    const notice = await screen.findByRole("region", { name: "Source updated" });
    expect(notice).toHaveTextContent("The question changed since you captured this note (version 1, now 2).");
    expect(notice).toHaveTextContent("When you captured itTell me about a time you worked under pressure.");
    expect(notice).toHaveTextContent("Now (version 2)Describe a shift when the pressure was on and you kept patients safe.");
    expect(notice).toHaveTextContent("Version 2: Clearer about patient safety.");
    // Above the snapshot.
    const snapshot = screen.getByRole("heading", { name: "Snapshot" });
    expect(notice.compareDocumentPosition(snapshot) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const before = noteStore.requests.length;
    await user.click(within(notice).getByRole("button", { name: "Mark reviewed (version 2)" }));
    expect(await screen.findByText("You marked it reviewed at version 2 on 15 November. Your note wasn't changed.")).toHaveFocus();
    expect(sent).toEqual([{ reviewed_version: 2 }]);
    expect(screen.queryByRole("region", { name: "Source updated" })).not.toBeInTheDocument();
    expect(noteStore.requests.slice(before)).toEqual([]); // no save of the note
    expect(noteStore.notes[0]!.body).toBe("Name the risk first.");
  });

  it("a source edited while reviewing keeps the notice, for the newer version", async () => {
    asNurse();
    const n = seed(fresh({}));
    serveReview((v) => fresh({ reviewed_version: v, current_version: 3, text: "The question changed again since you marked it reviewed at version 2 (now version 3). Review whether your note still fits." }));
    const { user } = renderApp(`/notes/${n.id}`, { signedIn: true });
    const notice = await screen.findByRole("region", { name: "Source updated" });
    await user.click(within(notice).getByRole("button", { name: "Mark reviewed (version 2)" }));
    await waitFor(() => expect(notice).toHaveTextContent("changed again since you marked it reviewed at version 2 (now version 3)"));
    expect(within(notice).getByRole("button", { name: "Mark reviewed (version 3)" })).toBeInTheDocument();
  });

  it("a note from before versions were captured says not known, never up to date", async () => {
    asNurse();
    const n = seed(fresh({ state: "unknown", captured_version: null, changes: [], change_notes: [], text: "Whether the question changed since isn't known: this note was captured before versions were recorded. It's version 2 now; mark it reviewed to be told about later changes." }));
    renderApp(`/notes/${n.id}`, { signedIn: true });
    const notice = await screen.findByRole("region", { name: "Source updated" });
    expect(within(notice).getByRole("heading", { name: "Source version not known" })).toBeInTheDocument();
    expect(notice).not.toHaveTextContent(/up to date/i);
    expect(within(notice).getByRole("button", { name: "Mark reviewed (version 2)" })).toBeInTheDocument();
  });

  it("a retired source is said, with nothing to mark", async () => {
    asNurse();
    const n = seed(fresh({ state: "retired", changes: [], change_notes: [], text: "This question was retired: Too vague. It still opens, and your note keeps what you captured." }));
    renderApp(`/notes/${n.id}`, { signedIn: true });
    const notice = await screen.findByRole("region", { name: "Source updated" });
    expect(within(notice).getByRole("heading", { name: "Source retired" })).toBeInTheDocument();
    expect(within(notice).queryByRole("button")).toBeNull();
    expect(screen.getByRole("heading", { name: "Snapshot" })).toBeInTheDocument(); // the note still opens
  });

  it("a lesson that doesn't keep its earlier wording lists what changed instead", async () => {
    asNurse();
    const n = seed(fresh({ kind: "lesson", comparable: false, changes: [], change_notes: ["Version 2: Reworded the SBAR example."], text: "The lesson changed since you captured this note (version 1, now 2). Review whether your note still fits. The lesson doesn't keep its earlier wording, so what changed can't be shown side by side." }));
    renderApp(`/notes/${n.id}`, { signedIn: true });
    const notice = await screen.findByRole("region", { name: "Source updated" });
    expect(notice).toHaveTextContent("can't be shown side by side");
    expect(notice).toHaveTextContent("What the lesson's authors said changed:Version 2: Reworded the SBAR example.");
    expect(within(notice).queryByText(/^When you captured it/)).toBeNull();
  });

  it("the notebook marks notes whose source changed, and filters to them", async () => {
    asNurse();
    seed(fresh({}));
    noteStore.notes.push(makeNote({ title: "Unrelated" }));
    const { user, router } = renderApp("/notes", { signedIn: true });
    const list = await within(await screen.findByRole("main")).findByRole("list");
    const changed = within(list).getByRole("link", { name: "Staying calm" }).closest("li")!;
    expect(changed).toHaveTextContent("Source updated");
    expect(within(list).getByRole("link", { name: "Unrelated" }).closest("li")).not.toHaveTextContent("Source updated");
    await user.click(screen.getByRole("checkbox", { name: "Source updated" }));
    await waitFor(() => expect(within(screen.getByRole("main")).getAllByRole("listitem")).toHaveLength(1));
    expect(router.state.location.search).toContain("updated=1");
  });
});

