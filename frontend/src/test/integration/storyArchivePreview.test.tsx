/**
 * Archiving a story shows what keeps it first (Volume 14, prompt 6; docs/LIFECYCLE.md): the kits
 * that chose it, its requirement links, the applications, reflections and answers that name it,
 * each kept; the button sends the plan it showed; a scope changed since shows the new plan and
 * does nothing; Unarchive needs no list, because it puts back what archiving kept.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Impact, LifecycleOutcome, Story } from "@/api/types";

import { renderApp } from "../render";
import { API, server } from "../server";

const now = () => new Date().toISOString();
const TITLE = "Two call lights at once";
function storyOut(over: Partial<Story> = {}): Story {
  return {
    id: "s1", title: TITLE, track: "registered-nurse", context: "work", competencies: ["prioritization"], tags: [],
    missing: [], target: null, revision: 1, archived: false, practice_count: 0, preview: "", updated_at: now(),
    situation: "", task: "", action: "", result: "", reflection: "", notes: "", evidence: "", short_version: "", long_version: "",
    questions: [], practice: [], privacy_hints: [], created_at: now(), ...over,
  };
}
const fx = (effect: Impact["effects"][number]["effect"], kind: string, title: string, id: string, note: string | null) => ({ effect, kind, title, id, note });
const plan = (kits = 1): Impact => ({
  action: "archive_story", target_id: "s1", title: TITLE, summary: "Archive this story",
  effects: [
    fx("archived", "story", TITLE, "s1", "Out of your story bank's list (under Archived); Unarchive brings it back as it was."),
    fx("kept", "requirement link", "Prioritises safely", "r1", "Still linked, labelled archived."),
    ...Array.from({ length: kits }, (_, i) => fx("kept", "interview-day kit", `Kit for Panel interview ${i + 1}`, `e${i}`, "Keeps what it prepared from it.")),
    fx("kept", "application", "Ward nurse at Mercy General", "a1", "Still linked."),
    fx("kept", "reflection", "Reflection on Phone screen", "e9", "Still names it."),
    fx("kept", "practice answer", "Tell me about a busy shift", "ans1", "Still records the story it used."),
  ],
  notes: ["Archiving isn't deleting: nothing is unlinked."], fingerprint: `story-${kits}`,
});
const outcome = (i: Impact): LifecycleOutcome => ({ ...i, done_at: now(), message: `Archived ${TITLE}.`, replayed: false, restorable_until: null });

function serve(opts: { changedOnce?: boolean } = {}) {
  let current = storyOut();
  let changed = opts.changedOnce ?? false;
  const sent: { path: string; body: unknown }[] = [];
  server.use(
    http.get(`${API}/api/v1/me/stories/s1`, () => HttpResponse.json(current)),
    http.get(`${API}/api/v1/me/stories/s1/revisions`, () => HttpResponse.json([])),
    http.get(`${API}/api/v1/me/stories/s1/archive-preview`, () => HttpResponse.json(plan())),
    http.post(`${API}/api/v1/me/stories/s1/archive-as-previewed`, async ({ request }) => {
      sent.push({ path: "archive-as-previewed", body: await request.json() });
      if (changed) {
        changed = false;
        return HttpResponse.json({ error: { code: "impact_changed", message: "Changed", request_id: "r", details: { current: plan(2) } } }, { status: 409 });
      }
      current = storyOut({ archived: true });
      return HttpResponse.json(outcome(plan()));
    }),
    http.post(`${API}/api/v1/me/stories/s1/unarchive`, () => {
      sent.push({ path: "unarchive", body: null });
      current = storyOut();
      return HttpResponse.json(current);
    }),
  );
  return sent;
}

describe("Archiving a story shows what keeps it first", () => {
  it("lists what uses it as kept, archives as previewed, and Unarchive brings it back", async () => {
    const sent = serve();
    const { user } = renderApp("/stories/s1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Archive…" }, { timeout: 3000 }));
    const list = await screen.findByRole("group", { name: "What this will do" });
    expect(within(list).getByRole("heading", { name: "Kept (5)" })).toBeInTheDocument();
    expect(list).toHaveTextContent("Interview-day kit: Kit for Panel interview 1 Keeps what it prepared from it.");
    expect(list).toHaveTextContent("Requirement link: Prioritises safely Still linked, labelled archived.");
    expect(sent).toEqual([]); // nothing until asked
    await user.click(within(list).getByRole("button", { name: "Archive this story" }));
    expect(await screen.findByText(/everything that used it keeps it\./)).toBeInTheDocument();
    expect(await screen.findByText(/STORY BANK · VERSION 1 · ARCHIVED/)).toBeInTheDocument();
    expect(sent[0]).toMatchObject({ path: "archive-as-previewed", body: { expected_fingerprint: "story-1" } });
    await user.click(screen.getByRole("button", { name: "Unarchive" }));
    await waitFor(() => expect(screen.queryByText(/· ARCHIVED/)).not.toBeInTheDocument());
    expect(sent.map((s) => s.path)).toEqual(["archive-as-previewed", "unarchive"]);
  });

  it("Cancel sends nothing", async () => {
    const sent = serve();
    const { user } = renderApp("/stories/s1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Archive…" }, { timeout: 3000 }));
    await user.click(within(await screen.findByRole("group", { name: "What this will do" })).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("group", { name: "What this will do" })).toBeNull();
    expect(sent).toEqual([]);
  });

  it("a scope that changed since the list shows the new list and does nothing until asked again", async () => {
    const sent = serve({ changedOnce: true });
    const { user } = renderApp("/stories/s1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Archive…" }, { timeout: 3000 }));
    const list = await screen.findByRole("group", { name: "What this will do" });
    await user.click(within(list).getByRole("button", { name: "Archive this story" }));
    expect(await within(list).findByText(/What this affects changed since you looked/)).toBeInTheDocument();
    expect(within(list).getByText(/Kit for Panel interview 2/)).toBeInTheDocument();
    expect(screen.queryByText(/· ARCHIVED/)).toBeNull();
    await user.click(within(list).getByRole("button", { name: "Archive this story" }));
    await waitFor(() => expect(sent).toHaveLength(2));
    expect(sent[1]).toMatchObject({ body: { expected_fingerprint: "story-2" } });
  });
});
