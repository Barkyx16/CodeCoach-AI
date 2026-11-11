/**
 * Where a story is used, and linking stories to an application (Volume 11, prompt 6;
 * docs/BACKLINKS.md). The story page lists the kits, applications and reflections that point at it,
 * with counts, a bounded list, archived records labelled, titles shown as plain text, and links that
 * carry a way back to the story. On an application, each story is linked or unlinked on its own
 * (never a whole list), an archived story that's still linked is shown so it can be unlinked, a
 * filter finds one among many, the limit is said, and a lost reply can be sent again safely.
 */
import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Application, Story, StorySummary, StoryUsedIn } from "@/api/types";

import { renderApp } from "../render";
import { API, server } from "../server";

const now = () => new Date().toISOString();
const NASTY = "<img src=x onerror=alert(1)>";

function storyOut(over: Partial<Story> = {}): Story {
  return {
    id: "s1", title: "Two call lights at once", track: "registered-nurse", context: "work", competencies: ["prioritization"], tags: [],
    missing: [], target: null, revision: 1, archived: false, practice_count: 0, preview: "", updated_at: now(),
    situation: "", task: "", action: "", result: "", reflection: "", notes: "", evidence: "", short_version: "", long_version: "",
    questions: [], practice: [], privacy_hints: [], created_at: now(), ...over,
  };
}
const summary = (id: string, title: string, over: Partial<StorySummary> = {}): StorySummary => ({
  id, title, track: "registered-nurse", context: "work", competencies: ["teamwork"], tags: [], missing: [], target: null, revision: 1,
  archived: false, practice_count: 0, preview: "", updated_at: now(), ...over,
});
const app = (over: Partial<Application> = {}): Application => ({
  id: "a1", employer: "Mercy General", role_title: "Ward nurse", stage: "interviewing", applied_on: null, next_action: "", next_action_due: null,
  target: null, archived: false, next_event: null, updated_at: now(), link: null, notes: "", notes_revision: 1, stories: [], events: [], history: [], created_at: now(), ...over,
});

function usedIn(over: Partial<StoryUsedIn> = {}): StoryUsedIn {
  return {
    applications: [{ id: "a1", role_title: "Ward nurse", employer: NASTY, stage: "interviewing", archived: true }],
    applications_total: 1,
    kits: [{ application_id: "a1", event_id: "e1", event_title: "Panel interview", event_on: "2026-11-20", role_title: "Ward nurse", employer: "Mercy General", application_archived: false }],
    kits_total: 1,
    reflections: [{ application_id: "a1", event_id: "e0", event_title: "Phone screen", event_on: "2026-11-01", role_title: "Ward nurse", employer: "Mercy General" }],
    reflections_total: 1,
    limit: 20,
    ...over,
  };
}

function serveStory(used: StoryUsedIn | "error") {
  let calls = 0;
  server.use(
    http.get(`${API}/api/v1/me/stories/s1`, () => HttpResponse.json(storyOut())),
    http.get(`${API}/api/v1/me/stories/s1/revisions`, () => HttpResponse.json([])),
    http.get(`${API}/api/v1/me/stories/s1/used-in`, () => {
      calls += 1;
      return used === "error" && calls === 1
        ? HttpResponse.json({ error: { code: "internal", message: "Something went wrong", request_id: "r" } }, { status: 500 })
        : HttpResponse.json(used === "error" ? usedIn() : used);
    }),
  );
}

describe("Where a story is used", () => {
  it("lists kits, applications and reflections with a way back, titles as plain text", async () => {
    serveStory(usedIn());
    const { user, router } = renderApp("/stories/s1", { signedIn: true });
    const card = (await screen.findByRole("heading", { name: "Where it's used" })).closest(".card") as HTMLElement;
    const kits = await within(card).findByRole("region", { name: "Interview kits (1)" });
    expect(kits).toHaveTextContent(/Panel interview · Ward nurse at Mercy General · .*20/);
    const apps = within(card).getByRole("region", { name: "Applications (1)" });
    expect(within(apps).getByRole("link", { name: `Ward nurse at ${NASTY}` })).toHaveAttribute("href", "/applications/a1");
    expect(apps).toHaveTextContent("Interviewing · archived");
    expect(card.querySelector("img")).toBeNull(); // a title is text, never markup
    expect(within(card).getByRole("region", { name: "Reflections (1)" })).toHaveTextContent("Phone screen");
    expect(card).toHaveTextContent("These point to this story; nothing is copied into them, and only you can see them.");

    await user.click(within(kits).getByRole("link", { name: "Panel interview" }));
    expect(router.state.location.pathname).toBe("/applications/a1/events/e1/kit");
    expect(router.state.location.state).toEqual({ from: "/stories/s1", fromLabel: "Back to your story" });
  });

  it("says when only some are shown, and when it isn't used anywhere", async () => {
    const many = Array.from({ length: 20 }, (_, i) => ({ id: `a${i}`, role_title: `Role ${i}`, employer: "Mercy General", stage: "saved" as const, archived: false }));
    serveStory(usedIn({ applications: many, applications_total: 23, kits: [], kits_total: 0, reflections: [], reflections_total: 0 }));
    const first = renderApp("/stories/s1", { signedIn: true });
    const apps = await screen.findByRole("region", { name: "Applications (23)" });
    expect(within(apps).getAllByRole("listitem")).toHaveLength(20);
    expect(apps).toHaveTextContent("The newest 20 of 23.");
    expect(screen.queryByRole("region", { name: /Interview kits/ })).not.toBeInTheDocument();
    first.unmount();

    serveStory(usedIn({ applications: [], applications_total: 0, kits: [], kits_total: 0, reflections: [], reflections_total: 0 }));
    renderApp("/stories/s1", { signedIn: true });
    expect(await screen.findByText(/Not in any interview kit, application or reflection yet\./)).toBeInTheDocument();
  });

  it("a failed read says so and can be tried again", async () => {
    serveStory("error");
    const { user } = renderApp("/stories/s1", { signedIn: true });
    const card = (await screen.findByRole("heading", { name: "Where it's used" })).closest(".card") as HTMLElement;
    await user.click(await within(card).findByRole("button", { name: /Try again/ }));
    expect(await within(card).findByRole("region", { name: "Interview kits (1)" })).toBeInTheDocument();
  });
});

describe("Linking stories to an application", () => {
  let sent: string[] = [];
  function serveApp(initial: Application, list: StorySummary[], { lose = false } = {}) {
    let current = initial;
    let lost = lose;
    sent = [];
    const titles = new Map([...list.map((s) => [s.id, s] as const)]);
    server.use(
      http.get(`${API}/api/v1/me/applications/a1`, () => HttpResponse.json(current)),
      http.get(`${API}/api/v1/me/stories`, () => HttpResponse.json(list)),
      http.patch(`${API}/api/v1/me/applications/a1`, () => { sent.push("PATCH"); return HttpResponse.json(current); }),
      http.all(`${API}/api/v1/me/applications/a1/stories/:sid`, ({ request, params }) => {
        const sid = String(params.sid);
        sent.push(`${request.method} ${sid}`);
        const has = current.stories.some((s) => s.id === sid);
        if (request.method === "PUT" && !has) {
          const s = titles.get(sid)!;
          current = { ...current, stories: [...current.stories, { id: sid, title: s.title, archived: s.archived }] };
        }
        if (request.method === "DELETE") current = { ...current, stories: current.stories.filter((s) => s.id !== sid) };
        if (lost) { lost = false; return HttpResponse.error(); } // it went through; the reply didn't
        return HttpResponse.json(current);
      }),
    );
  }

  it("links and unlinks one story at a time by keyboard, keeping focus, and shows the archived one still linked", async () => {
    serveApp(app({ stories: [{ id: "old", title: "An archived story", archived: true }] }), [summary("s1", "Two call lights"), summary("s2", "Night handover")]);
    const { user } = renderApp("/applications/a1", { signedIn: true });
    const card = (await screen.findByRole("heading", { name: "Linked preparation" }, { timeout: 3000 })).closest(".card") as HTMLElement;
    const archived = await within(card).findByRole("checkbox", { name: /An archived story \(archived\)/ });
    expect(archived).toBeChecked();
    expect(within(card).getByText(/Linked \(1\):/)).toHaveTextContent("Linked (1): An archived story (archived)");

    const order = () => within(card).getAllByRole("checkbox").map((c) => c.closest("label")!.textContent);
    const before = order();
    const box = within(card).getByRole("checkbox", { name: /Night handover/ });
    act(() => box.focus());
    await user.keyboard(" ");
    await waitFor(() => expect(within(card).getByText(/Linked \(2\):/)).toBeInTheDocument());
    expect(box).toBeChecked();
    expect(box).toHaveFocus();
    expect(order()).toEqual(before); // the list doesn't reorder, so nothing jumps under the keyboard
    await user.click(archived);
    await waitFor(() => expect(within(card).queryByRole("checkbox", { name: /An archived story/ })).not.toBeInTheDocument());
    expect(sent).toEqual(["PUT s2", "DELETE old"]); // one story each time, never the whole list
  });

  it("after a lost reply, Try again sends the same link once more and it's linked once", async () => {
    serveApp(app(), [summary("s1", "Two call lights")], { lose: true });
    const { user } = renderApp("/applications/a1", { signedIn: true });
    await user.click(await screen.findByRole("checkbox", { name: /Two call lights/ }, { timeout: 3000 }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No reply came, so it isn't known whether “Two call lights” was linked. Trying again is safe: it's done once either way.");
    await user.click(within(alert).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(screen.getByRole("checkbox", { name: /Two call lights/ })).toBeChecked();
    expect(sent.filter((s) => s.startsWith("PUT"))).toEqual(["PUT s1", "PUT s1"]);
    expect(screen.getByText(/Linked \(1\):/)).toHaveTextContent("Linked (1): Two call lights"); // once, not twice
  });

  it("finds a story among many, and says the limit when twenty are linked", async () => {
    const list = Array.from({ length: 21 }, (_, i) => summary(`s${i}`, i === 7 ? "Medication error at night" : `Story number ${i}`));
    serveApp(app({ stories: list.slice(0, 20).map((s) => ({ id: s.id, title: s.title, archived: false })) }), list);
    const { user } = renderApp("/applications/a1", { signedIn: true });
    const find = await screen.findByLabelText("Find a story", undefined, { timeout: 3000 });
    await user.type(find, "medication NIGHT");
    expect(screen.getByText("1 of 21 shown.")).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox", { name: /Medication error|Story number/ })).toHaveLength(1);
    await user.clear(find);
    const last = screen.getByRole("checkbox", { name: /Story number 20/ });
    expect(last).toBeDisabled();
    expect(last).toHaveAccessibleDescription("Up to 20 stories per application: unlink one to add another.");
    expect(screen.getByRole("checkbox", { name: /Story number 0/ })).toBeEnabled(); // a linked one can still be unlinked
  });
});
