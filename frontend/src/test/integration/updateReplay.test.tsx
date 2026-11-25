/**
 * A save whose reply was lost is recovered as the learner's own success (Volume 8, prompt 3). The
 * page sends the same save again with the same key; the server (here, a stand-in that keeps
 * receipts like the real one) answers "went through as version N". If the record changed after
 * that, the page compares instead of replacing; a real conflict still shows both versions; newer
 * typing stays unsaved and is saved after.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Note, Story } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asUser = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const now = () => new Date().toISOString();

function story(over: Partial<Story> = {}): Story {
  return {
    id: "s1", title: "Two call lights at once", track: "registered-nurse", context: "work", competencies: ["prioritization"], tags: [],
    missing: [], target: null, revision: 1, archived: false, practice_count: 0, preview: "On a night shift two patients rang.", updated_at: now(),
    situation: "On a night shift two patients rang.", task: "Decide who to see first.", action: "I checked who was at higher risk.",
    result: "Both were seen within five minutes.", reflection: "", notes: "", evidence: "", short_version: "", long_version: "",
    questions: [], practice: [], privacy_hints: [], created_at: now(), ...over,
  } as Story;
}

/** A stand-in for a revision-checked save endpoint that keeps receipts, as the server does. */
function receiptsFor<T extends { revision: number }>(start: T) {
  const state = { current: start, dropNextReply: false, patches: [] as Record<string, unknown>[] };
  const receipts = new Map<string, { base: number; accepted: number; sent: string }>();
  function handle(body: Record<string, unknown>, base: number, apply: (cur: T) => T) {
    state.patches.push(body);
    const key = body.client_request_id as string | undefined;
    const sent = JSON.stringify({ ...body, client_request_id: undefined });
    const r = key ? receipts.get(key) : undefined;
    if (r) {
      if (r.base !== base || r.sent !== sent) {
        return HttpResponse.json({ error: { code: "idempotency_key_reused", message: "reused", request_id: "r" } }, { status: 409 });
      }
      return HttpResponse.json({ ...state.current, save_replay: { accepted_revision: r.accepted, current_revision: state.current.revision } });
    }
    if (base !== state.current.revision) return null; // the caller answers with its own conflict
    state.current = apply(state.current);
    if (key) receipts.set(key, { base, accepted: state.current.revision, sent });
    if (state.dropNextReply) {
      state.dropNextReply = false;
      return HttpResponse.error(); // saved, but the reply never arrives
    }
    return HttpResponse.json({ ...state.current, save_replay: null });
  }
  return { state, handle };
}

function fakeStory() {
  const fake = receiptsFor(story());
  server.use(
    http.get(`${API}/api/v1/me/stories/:id`, () => HttpResponse.json(fake.state.current)),
    http.get(`${API}/api/v1/me/stories/:id/revisions`, () => HttpResponse.json([])),
    http.patch(`${API}/api/v1/me/stories/:id`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      const base = body.expected_revision as number;
      const out = fake.handle(body, base, (cur) => {
        const fields = Object.fromEntries(Object.entries(body).filter(([k]) => !["expected_revision", "reason", "clear_target", "client_request_id"].includes(k)));
        return { ...cur, ...(fields as Partial<Story>), revision: cur.revision + 1, updated_at: now() };
      });
      return out ?? HttpResponse.json({ error: { code: "stale_revision", message: "Changed", request_id: "r",
        details: { current_revision: fake.state.current.revision, current: fake.state.current } } }, { status: 409 });
    }),
  );
  return fake;
}

describe("a save whose reply was lost", () => {
  it("is recovered as the learner's own save, not a conflict with it", async () => {
    asUser();
    const fake = fakeStory();
    const { user } = renderApp("/stories/s1", { signedIn: true });
    const result = await screen.findByLabelText("Result");
    await user.clear(result);
    await user.type(result, "Both were seen in four minutes.");
    fake.state.dropNextReply = true;
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(document.querySelector(".inline-error")).not.toBeNull()); // no reply came
    expect(fake.state.current.revision).toBe(2); // it was saved
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Your earlier save went through as version 2.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Edit conflict" })).not.toBeInTheDocument();
    const [a, b] = fake.state.patches;
    expect(a?.client_request_id).toBe(b?.client_request_id); // the same save, sent again
    expect(fake.state.current.revision).toBe(2); // not saved twice
    expect(screen.getByLabelText("Result")).toHaveValue("Both were seen in four minutes.");
  });

  it("when the story changed on another device after it, both are shown and nothing is replaced", async () => {
    asUser();
    const fake = fakeStory();
    const { user } = renderApp("/stories/s1", { signedIn: true });
    const result = await screen.findByLabelText("Result");
    await user.clear(result);
    await user.type(result, "Mine, from the laptop.");
    fake.state.dropNextReply = true;
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(document.querySelector(".inline-error")).not.toBeNull());
    // Meanwhile, the phone saves version 3 over it.
    fake.state.current = { ...fake.state.current, result: "Theirs, from the phone.", revision: 3, updated_at: now() };
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    const conflict = await screen.findByRole("region", { name: "Edit conflict" });
    expect(within(conflict).getByText(/Your save went through as version 2\. This story was changed after that/)).toBeInTheDocument();
    expect(within(conflict).getByText("Mine, from the laptop.")).toBeInTheDocument();
    expect(within(conflict).getByText("Theirs, from the phone.")).toBeInTheDocument();
    expect(screen.getByLabelText("Result")).toHaveValue("Mine, from the laptop."); // the page isn't replaced
    expect(fake.state.current.result).toBe("Theirs, from the phone."); // nor the newer save
    // The learner chooses: keep the newer saved one.
    await user.click(within(conflict).getByRole("button", { name: /Use the saved|saved version/i }));
    await waitFor(() => expect(screen.getByLabelText("Result")).toHaveValue("Theirs, from the phone."));
  });

  it("a real conflict from another tab still says this page's version wasn't saved", async () => {
    asUser();
    const fake = fakeStory();
    fake.state.current = { ...fake.state.current, result: "Another tab.", revision: 2 };
    const { user } = renderApp("/stories/s1", { signedIn: true });
    const result = await screen.findByLabelText("Result");
    // The page loaded version 2 here, so make it stale: another save lands first.
    fake.state.current = { ...fake.state.current, result: "A third tab.", revision: 3 };
    await user.clear(result);
    await user.type(result, "This tab.");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    const conflict = await screen.findByRole("region", { name: "Edit conflict" });
    expect(within(conflict).getByText(/This story was saved in another tab or on another device/)).toBeInTheDocument();
    expect(within(conflict).getByText("Your version (not saved)")).toBeInTheDocument();
  });
});

describe("a note autosave whose reply was lost, with typing after it", () => {
  it("sends that save again first, then the newer text: no conflict with itself", async () => {
    asUser();
    const note: Note = {
      id: "n1", title: "Handover", body: "first", reflection: "", tags: [], revision: 1, pinned: false, archived: false,
      source: null, excerpt: null, excerpt_kind: null, key_points: null, created_at: now(), updated_at: now(), deleted_at: null,
    } as unknown as Note;
    const fake = receiptsFor(note);
    server.use(
      http.get(`${API}/api/v1/me/notes/:id`, () => HttpResponse.json(fake.state.current)),
      http.get(`${API}/api/v1/me/notes`, () => HttpResponse.json({ items: [fake.state.current], total: 1, page: 1, page_size: 20 })),
      http.patch(`${API}/api/v1/me/notes/:id`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const out = fake.handle(body, body.base_revision as number, (cur) => ({ ...cur, body: body.body as string, revision: cur.revision + 1 }));
        return out ?? HttpResponse.json({ error: { code: "note_conflict", message: "Changed", request_id: "r", details: { current: fake.state.current } } }, { status: 409 });
      }),
    );
    const { user } = renderApp("/notes/n1", { signedIn: true });
    const body = await screen.findByLabelText(/^Note$|Body|Your note/);
    fake.state.dropNextReply = true;
    await user.clear(body);
    await user.type(body, "second");
    await waitFor(() => expect(fake.state.current.revision).toBe(2), { timeout: 4000 }); // saved, reply lost
    await user.type(body, " and third");
    await waitFor(() => expect(fake.state.current.body).toBe("second and third"), { timeout: 6000 });
    expect(screen.queryByRole("region", { name: "Edit conflict" })).not.toBeInTheDocument();
    const keys = fake.state.patches.map((p) => p.client_request_id);
    expect(keys[1]).toBe(keys[0]); // the lost save, sent again exactly
    expect(fake.state.patches[1]?.body).toBe(fake.state.patches[0]?.body);
    expect(fake.state.patches.at(-1)!.base_revision).toBe(2); // the newer text, on top of it
  });
});
