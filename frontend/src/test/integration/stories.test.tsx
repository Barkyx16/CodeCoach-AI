import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Story, StoryAssist } from "@/api/types";

import { nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asUser = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const now = () => new Date().toISOString();
const QUESTION = "/careers/registered-nurse/questions/m-pressure-0";

function story(over: Partial<Story> = {}): Story {
  return {
    id: "s1", title: "Two call lights at once", track: "registered-nurse", context: "work", competencies: ["prioritization"], tags: ["night shift"],
    missing: [], target: null, revision: 1, archived: false, practice_count: 0, preview: "On a night shift two patients rang.", updated_at: now(),
    situation: "On a night shift two patients rang.", task: "Decide who to see first.", action: "I checked who was at higher risk and asked a colleague to help.",
    result: "Both were seen within five minutes.", reflection: "", notes: "", evidence: "", short_version: "", long_version: "",
    questions: [], practice: [], privacy_hints: [], created_at: now(), ...over,
  };
}

/** A small stand-in for the story API that records what was sent. */
function fakeStories(initial: Story[] = [story()]) {
  const stories = new Map(initial.map((s) => [s.id, s]));
  const sent: { method: string; url: string; body: unknown }[] = [];
  server.use(
    http.get(`${API}/api/v1/me/stories`, ({ request }) => {
      sent.push({ method: "GET", url: request.url, body: null });
      return HttpResponse.json([...stories.values()]);
    }),
    http.get(`${API}/api/v1/me/stories/:id`, ({ params }) => {
      const s = stories.get(String(params.id));
      return s ? HttpResponse.json(s) : HttpResponse.json({ error: { code: "not_found", message: "Story not found", request_id: "r" } }, { status: 404 });
    }),
    http.post(`${API}/api/v1/me/stories`, async ({ request }) => {
      const body = (await request.json()) as Partial<Story>;
      sent.push({ method: "POST", url: request.url, body });
      const s = story({ ...body, id: "s-new", target: null, questions: [] } as Partial<Story>);
      stories.set(s.id, s);
      return HttpResponse.json(s, { status: 201 });
    }),
    http.patch(`${API}/api/v1/me/stories/:id`, async ({ params, request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      sent.push({ method: "PATCH", url: request.url, body });
      const s = stories.get(String(params.id))!;
      if (body.expected_revision !== s.revision) {
        return HttpResponse.json({ error: { code: "stale_revision", message: "Changed", request_id: "r", details: { current_revision: s.revision, current: s } } }, { status: 409 });
      }
      const fields = Object.fromEntries(Object.entries(body).filter(([k]) => !["expected_revision", "reason", "clear_target"].includes(k)));
      const next = { ...s, ...(fields as Partial<Story>), revision: s.revision + 1 };
      stories.set(s.id, next);
      return HttpResponse.json(next);
    }),
    http.get(`${API}/api/v1/me/stories/:id/revisions`, () => HttpResponse.json([
      { revision: 2, reason: "edited", created_at: now(), fields: { title: "Two call lights at once", result: "Both were seen." } },
      { revision: 1, reason: "created", created_at: now(), fields: { title: "Call lights", situation: "The original wording." } },
    ])),
  );
  return { sent, stories };
}

describe("the story bank", () => {
  it("lists stories, searches on the server and says what isn't written yet", async () => {
    asUser();
    const { sent } = fakeStories([story(), story({ id: "s2", title: "A missed handover", missing: ["task", "result"], competencies: ["mistakes"] })]);
    const { user } = renderApp("/stories", { signedIn: true });
    expect(await screen.findByRole("link", { name: "A missed handover" })).toBeInTheDocument();
    expect(screen.getByText(/Not written yet: Task, Result/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Search your stories"), "handover");
    await user.selectOptions(screen.getByLabelText("Competency"), "mistakes");
    await waitFor(() => expect(sent.some((r) => r.url.includes("q=handover") && r.url.includes("competency=mistakes"))).toBe(true));
  });

  it("writes a new story and keeps unsaved edits on the device", async () => {
    asUser();
    const { sent } = fakeStories([]);
    const { user, router, unmount } = renderApp("/stories/new", { signedIn: true });
    await user.type(await screen.findByLabelText("Title"), "Covering a short-staffed ward");
    await user.type(screen.getByLabelText("Situation"), "Two nurses called in sick.");
    expect(screen.getByText("Unsaved changes, kept on this device")).toBeInTheDocument();
    unmount();

    // Back later: the unsaved text is offered, not silently applied.
    const again = renderApp("/stories/new", { signedIn: true });
    expect(await screen.findByText(/You have unsaved changes to this story/)).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("");
    await again.user.click(screen.getByRole("button", { name: "Restore them" }));
    expect(screen.getByLabelText("Title")).toHaveValue("Covering a short-staffed ward");
    await again.user.click(screen.getByLabelText("Teamwork"));
    await again.user.click(screen.getByRole("button", { name: "Save story" }));
    await waitFor(() => expect(again.router.state.location.pathname).toBe("/stories/s-new"));
    expect(sent.find((r) => r.method === "POST")?.body).toMatchObject({ title: "Covering a short-staffed ward", situation: "Two nurses called in sick.", competencies: ["teamwork"], track: "registered-nurse" });
    expect(router).toBeDefined();
  });

  it("saves only what changed, and handles a save from another tab without losing anything", async () => {
    asUser();
    const { sent, stories } = fakeStories();
    const { user } = renderApp("/stories/s1", { signedIn: true });
    const result = await screen.findByLabelText("Result");
    await user.clear(result);
    await user.type(result, "Both were seen in five minutes.");
    stories.set("s1", { ...stories.get("s1")!, revision: 2, result: "Saved on the other device." }); // saved elsewhere meanwhile
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    // Both versions side by side, only the part that differs, and nothing lost or overwritten.
    const conflict = await screen.findByRole("region", { name: "Edit conflict" });
    expect(conflict).toHaveTextContent("This story was saved in another tab or on another device (version 2");
    expect(within(conflict).getByText("Both were seen in five minutes.")).toBeInTheDocument();
    expect(within(conflict).getByText("Saved on the other device.")).toBeInTheDocument();
    expect(screen.getByLabelText("Result")).toHaveValue("Both were seen in five minutes.");
    await user.click(within(conflict).getByRole("button", { name: "Keep mine as the newest version" }));
    expect(await screen.findByText("Saved as version 3.")).toBeInTheDocument();
    const patches = sent.filter((r) => r.method === "PATCH").map((r) => r.body);
    expect(patches).toEqual([
      { clear_target: false, result: "Both were seen in five minutes.", expected_revision: 1, reason: "edited", client_request_id: expect.any(String) },
      { clear_target: false, result: "Both were seen in five minutes.", expected_revision: 2, reason: "edited", client_request_id: expect.any(String) },
    ]);
    // Two different saves (another base revision): two keys, so the second isn't taken for a retry.
    const keys = patches.map((p) => (p as { client_request_id: string }).client_request_id);
    expect(new Set(keys).size).toBe(2);
  });

  it("writing help proposes side by side, and nothing changes until it's accepted and saved", async () => {
    asUser();
    const { sent } = fakeStories([story({ action: "Basically we really reorganised the rota." })]);
    const assist: StoryAssist = {
      action: "shorten", method: "Built-in writing check: fixed rules, not AI. Your story isn't sent anywhere.",
      proposals: [{ field: "action", original: "Basically we really reorganised the rota.", proposed: "We reorganised the rota.", changes: ["Removed “basically”, “really”"] }],
      questions: ["Action: this describes what the team did. Which parts did you do yourself?"],
    };
    let assistBody: unknown = null;
    server.use(http.post(`${API}/api/v1/me/stories/s1/assist`, async ({ request }) => { assistBody = await request.json(); return HttpResponse.json(assist); }));
    const { user } = renderApp("/stories/s1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Suggest a shorter version" }));
    const proposal = await screen.findByRole("region", { name: "Suggestion for Action" });
    expect(within(proposal).getByText("Basically we really reorganised the rota.")).toBeInTheDocument();
    expect(within(proposal).getByText("We reorganised the rota.")).toBeInTheDocument();
    expect(screen.getByText(/Which parts did you do yourself/)).toBeInTheDocument();
    expect(assistBody).toMatchObject({ action: "shorten", action_text: "Basically we really reorganised the rota." });
    expect(sent.filter((r) => r.method === "PATCH")).toHaveLength(0);
    await user.click(within(proposal).getByRole("button", { name: "Use this version" }));
    expect(screen.getByLabelText("Action")).toHaveValue("We reorganised the rota.");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(sent.find((r) => r.method === "PATCH")?.body).toMatchObject({ action: "We reorganised the rota.", reason: "assisted" }));
  });

  it("shows every saved version and restores one as a new version", async () => {
    asUser();
    fakeStories([story({ revision: 2 })]);
    let restored: unknown = null;
    server.use(http.post(`${API}/api/v1/me/stories/s1/revisions/1/restore`, async ({ request }) => {
      restored = await request.json();
      return HttpResponse.json(story({ revision: 3, title: "Call lights", situation: "The original wording." }));
    }));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { user } = renderApp("/stories/s1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Version 1" }));
    expect(screen.getByText("The original wording.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Restore this version" }));
    expect(restored).toEqual({ expected_revision: 2 });
    await waitFor(() => expect(screen.getByLabelText("Situation")).toHaveValue("The original wording."));
  });

  it("shows untrusted text as text and points out details that may identify someone", async () => {
    asUser();
    fakeStories([story({ title: "<img src=x onerror=alert(1)>", privacy_hints: ["“Mr. Smith” may identify someone."] })]);
    renderApp("/stories/s1", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "<img src=x onerror=alert(1)>" })).toBeInTheDocument();
    expect(screen.getByText("“Mr. Smith” may identify someone.")).toBeInTheDocument();
    expect(document.querySelector("img[src='x']")).toBeNull();
  });
});

describe("practising with a story", () => {
  it("starts a draft from the story, sends the story with the answer, and never edits the story", async () => {
    asUser();
    const { sent } = fakeStories();
    let answerBody: unknown = null;
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, async ({ request }) => {
      answerBody = await request.json();
      return HttpResponse.json({ ...nurseAnswer, story_id: "s1" }, { status: 201 });
    }));
    const { user } = renderApp(QUESTION, { signedIn: true });
    await user.click(await screen.findByText("Practise with one of your stories"));
    await user.click(await screen.findByRole("radio", { name: /Two call lights at once/ }));
    expect(await screen.findByText(/The story isn't changed/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start my answer from this story" }));
    const box = screen.getByRole("textbox", { name: "Your answer" });
    expect((box as HTMLTextAreaElement).value).toContain("I checked who was at higher risk");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await waitFor(() => expect(answerBody).toMatchObject({ story_id: "s1" }));
    expect(sent.filter((r) => r.method === "PATCH")).toHaveLength(0);
  });
});

describe("exact save state", () => {
  it("a save that answers after more typing keeps that typing, and doesn't call it saved", async () => {
    asUser();
    fakeStories();
    let release!: () => void;
    const answered = new Promise<void>((r) => { release = r; });
    const bodies: Record<string, unknown>[] = [];
    server.use(http.patch(`${API}/api/v1/me/stories/:id`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      bodies.push(body);
      if (bodies.length === 1) await answered; // the first save is slow
      return HttpResponse.json(story({ revision: 1 + bodies.length, result: String(body.result) }));
    }));
    const { user } = renderApp("/stories/s1", { signedIn: true });
    const result = await screen.findByLabelText("Result");
    await user.clear(result);
    await user.type(result, "First.");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await user.type(result, " Second."); // typed while that save is on its way
    release();
    await waitFor(() => expect(screen.getByText("Unsaved changes, kept on this device")).toBeInTheDocument());
    expect(screen.getByLabelText("Result")).toHaveValue("First. Second."); // not replaced by the server's copy
    expect(screen.queryByText(/Saved as version/)).toBeNull();
    // The next save sends the newer text against the version the first save made.
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Saved as version 3.")).toBeInTheDocument();
    expect(bodies[1]).toMatchObject({ result: "First. Second.", expected_revision: 2 });
  });

  it("restoring a copy kept against an older version compares first, and saves nothing on its own", async () => {
    asUser();
    const { sent } = fakeStories([story({ revision: 2, result: "Saved later on the other device." })]);
    const { fromStory, storyDraftKey } = await import("@/features/stories/storyForm");
    window.localStorage.setItem(storyDraftKey(nurse.id, "s1"), JSON.stringify({
      form: { ...fromStory(story()), result: "Kept on this device." }, base: 1, at: now(),
    }));
    const { user } = renderApp("/stories/s1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Restore them" }));
    const conflict = await screen.findByRole("region", { name: "Edit conflict" });
    expect(within(conflict).getByText("Kept on this device.")).toBeInTheDocument();
    expect(within(conflict).getByText("Saved later on the other device.")).toBeInTheDocument();
    expect(sent.filter((r) => r.method === "PATCH")).toHaveLength(0);
    await user.click(within(conflict).getByRole("button", { name: "Use the saved version" }));
    expect(screen.getByLabelText("Result")).toHaveValue("Saved later on the other device.");
    expect(window.localStorage.getItem(storyDraftKey(nurse.id, "s1"))).toBeNull();
  });
});
