/**
 * Records changed elsewhere (Volume 11, prompt 9; docs/FRESHNESS.md), for stories. Back in the tab
 * (or a hint from another tab), a page with no unsaved changes shows the newer version; a page with
 * changes keeps them and offers the comparison; an archive elsewhere changes only the flag and a
 * later save doesn't undo it; a deletion keeps the text with Copy or Save as a new story, never
 * recreating the old one; an older reply arriving late changes nothing. Another tab's hint updates a
 * clean list at once; another account's hint, or a malformed one, is ignored; hints carry no content.
 */
import { focusManager, onlineManager } from "@tanstack/react-query";
import { act, screen, waitFor, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";

import type { Story } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = () => new Date().toISOString();
const story = (over: Partial<Story> = {}): Story => ({
  id: "s1", title: "Two call lights", track: "registered-nurse", context: "work", competencies: [], tags: [], missing: [], target: null, revision: 1,
  archived: false, practice_count: 0, preview: "", updated_at: now(), situation: "A busy night shift.", task: "Decide who to see first.",
  action: "I checked who was at higher risk.", result: "Both seen within five minutes.", reflection: "", notes: "", evidence: "",
  short_version: "", long_version: "", questions: [], practice: [], privacy_hints: [], created_at: now(), ...over,
});

let db: { current: Story | null; gets: number; listGets: number; sent: { method: string; path: string; body: unknown }[]; stale: Story | null };
function serve(initial = story()) {
  db = { current: initial, gets: 0, listGets: 0, sent: [], stale: null };
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/me/stories`, () => { db.listGets += 1; return HttpResponse.json(db.current && !db.current.archived ? [db.current] : []); }),
    http.get(`${API}/api/v1/me/stories/s1`, () => {
      db.gets += 1;
      if (db.stale) return HttpResponse.json(db.stale); // an older reply, late
      return db.current ? HttpResponse.json(db.current) : HttpResponse.json({ error: { code: "not_found", message: "Story not found", request_id: "r" } }, { status: 404 });
    }),
    http.get(`${API}/api/v1/me/stories/s1/revisions`, () => HttpResponse.json([])),
    http.get(`${API}/api/v1/me/stories/s1/used-in`, () => HttpResponse.json({ applications: [], applications_total: 0, kits: [], kits_total: 0, reflections: [], reflections_total: 0, limit: 20 })),
    http.patch(`${API}/api/v1/me/stories/s1`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      db.sent.push({ method: "PATCH", path: "/s1", body });
      const c = db.current!;
      if (body.expected_revision !== c.revision) {
        return HttpResponse.json({ error: { code: "stale_revision", message: "Changed", request_id: "r", details: { current_revision: c.revision, current: c } } }, { status: 409 });
      }
      const fields = Object.fromEntries(Object.entries(body).filter(([k]) => !["expected_revision", "reason", "clear_target", "client_request_id"].includes(k)));
      db.current = { ...c, ...(fields as Partial<Story>), revision: c.revision + 1 };
      return HttpResponse.json(db.current);
    }),
    http.post(`${API}/api/v1/me/stories`, async ({ request }) => {
      const body = (await request.json()) as Partial<Story>;
      db.sent.push({ method: "POST", path: "/", body });
      return HttpResponse.json(story({ ...body, id: "s-new", revision: 1 }), { status: 201 });
    }),
    http.post(`${API}/api/v1/me/stories/s1/:action`, ({ params }) => { db.sent.push({ method: "POST", path: `/s1/${String(params.action)}`, body: null }); return HttpResponse.json(db.current); }),
  );
}
const elsewhere = (over: Partial<Story>) => { db.current = { ...db.current!, ...over, updated_at: now() }; };
const backToTab = () => act(() => { focusManager.setFocused(false); focusManager.setFocused(true); });
afterEach(() => { focusManager.setFocused(undefined); onlineManager.setOnline(true); });

describe("A story changed in another tab or on another device", () => {
  it("shows the newer version when nothing here is unsaved", async () => {
    serve();
    renderApp("/stories/s1", { signedIn: true });
    expect(await screen.findByDisplayValue("Two call lights", undefined, { timeout: 3000 })).toBeInTheDocument();
    elsewhere({ title: "Two call lights at once", revision: 2 });
    await backToTab();
    expect(await screen.findByDisplayValue("Two call lights at once")).toBeInTheDocument();
    expect(screen.getByText("Updated to version 2, saved in another tab or on another device.")).toBeInTheDocument();
    expect(screen.getByText(/VERSION 2/)).toBeInTheDocument();
  });

  it("asks again when the connection comes back, having missed the change", async () => {
    serve();
    renderApp("/stories/s1", { signedIn: true });
    expect(await screen.findByDisplayValue("Two call lights", undefined, { timeout: 3000 })).toBeInTheDocument();
    act(() => { onlineManager.setOnline(false); });
    elsewhere({ title: "Renamed while offline", revision: 2 });
    act(() => { onlineManager.setOnline(true); });
    expect(await screen.findByDisplayValue("Renamed while offline")).toBeInTheDocument();
  });

  it("keeps unsaved changes and offers the saved version to compare", async () => {
    serve();
    const { user } = renderApp("/stories/s1", { signedIn: true });
    const situation = await screen.findByLabelText("Situation", undefined, { timeout: 3000 });
    await user.clear(situation);
    await user.type(situation, "My own words, not saved yet.");
    elsewhere({ title: "Renamed elsewhere", situation: "Their words.", revision: 2 });
    await backToTab();
    expect(await screen.findByText(/This story was saved somewhere else \(version 2\) since you opened it\. Your changes are still here, not saved\./)).toBeInTheDocument();
    expect(situation).toHaveValue("My own words, not saved yet."); // nothing replaced
    expect(screen.getByDisplayValue("Two call lights")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Compare with the saved version" }));
    expect(screen.getByText("Their words.")).toBeInTheDocument(); // the real saved version, beside mine
    await user.click(screen.getByRole("button", { name: "Keep mine as the newest version" }));
    await waitFor(() => expect(db.current!.revision).toBe(3));
    const patch = db.sent.find((s) => s.method === "PATCH")!.body as Record<string, unknown>;
    expect(patch.expected_revision).toBe(2); // saved over the version seen, knowingly
    expect(patch.situation).toBe("My own words, not saved yet.");
  });

  it("an archive elsewhere changes only the flag, and a later save doesn't undo it", async () => {
    serve();
    const { user } = renderApp("/stories/s1", { signedIn: true });
    const task = await screen.findByLabelText("Task", undefined, { timeout: 3000 });
    await user.type(task, " Quickly.");
    elsewhere({ archived: true });
    await backToTab();
    expect(await screen.findByText("Archived in another tab or on another device. It's kept, and hidden from your list.")).toBeInTheDocument();
    expect(screen.getByText(/ARCHIVED/)).toBeInTheDocument();
    expect(task).toHaveValue("Decide who to see first. Quickly.");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(db.current!.revision).toBe(2));
    expect(db.current!.archived).toBe(true);
    expect(db.sent.map((s) => `${s.method} ${s.path}`)).toEqual(["PATCH /s1"]); // no unarchive, no archive field
    expect(Object.keys(db.sent[0]!.body as object)).not.toContain("archived");
  });

  it("a deletion elsewhere keeps the text, offers Copy or a new story, and never recreates the old one", async () => {
    serve();
    const { user, router } = renderApp("/stories/s1", { signedIn: true });
    const writeText = vi.spyOn(navigator.clipboard, "writeText"); // user-event's clipboard stand-in
    const result = await screen.findByLabelText("Result", undefined, { timeout: 3000 });
    await user.clear(result);
    await user.type(result, "Both were seen; I wrote it down.");
    db.current = null;
    await backToTab();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("This story was deleted, or isn't available to this account any more. Your text below is still on this page and kept on this device; it isn't saved anywhere else.");
    expect(result).toHaveValue("Both were seen; I wrote it down.");
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Delete…" })).toBeNull();
    await user.click(within(alert).getByRole("button", { name: "Copy my text" }));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Both were seen; I wrote it down."));
    await user.click(within(alert).getByRole("button", { name: "Save it as a new story" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/stories/s-new"));
    expect(db.sent.map((s) => `${s.method} ${s.path}`)).toEqual(["POST /"]); // a new story; nothing sent to the old one
    expect((db.sent[0]!.body as Partial<Story>).result).toBe("Both were seen; I wrote it down.");
  });

  it("a comparison still open when the story is deleted is withdrawn, and the text stays", async () => {
    serve();
    const { user } = renderApp("/stories/s1", { signedIn: true });
    const situation = await screen.findByLabelText("Situation", undefined, { timeout: 3000 });
    await user.clear(situation);
    await user.type(situation, "My own words, not saved yet.");
    elsewhere({ title: "Renamed elsewhere", revision: 2 });
    await backToTab();
    await user.click(await screen.findByRole("button", { name: "Compare with the saved version" }));
    expect(screen.getByRole("button", { name: "Keep mine as the newest version" })).toBeInTheDocument();
    db.current = null;
    await backToTab();
    expect(await screen.findByText(/This story was deleted/)).toBeInTheDocument();
    expect(screen.getAllByRole("alert")).toHaveLength(1); // the deletion; the comparison is gone
    expect(screen.queryByRole("button", { name: "Keep mine as the newest version" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Use the saved version" })).toBeNull();
    expect(situation).toHaveValue("My own words, not saved yet.");
    expect(db.sent).toEqual([]);
  });

  it("an older reply arriving late changes nothing", async () => {
    serve();
    const { user } = renderApp("/stories/s1", { signedIn: true });
    const title = await screen.findByLabelText("Title", undefined, { timeout: 3000 });
    await user.type(title, " (night shift)");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Saved as version 2.")).toBeInTheDocument();
    db.stale = story(); // version 1, from before the save
    await backToTab();
    await waitFor(() => expect(db.gets).toBeGreaterThanOrEqual(2));
    expect(title).toHaveValue("Two call lights (night shift)");
    expect(screen.getByText(/VERSION 2/)).toBeInTheDocument();
    expect(screen.queryByText(/saved somewhere else/)).toBeNull();
  });
});

describe("Hints between this browser's tabs", () => {
  it("another tab's hint updates a clean list at once; another account's or a malformed one is ignored", async () => {
    serve();
    renderApp("/stories", { signedIn: true });
    expect(await screen.findByRole("link", { name: "Two call lights" }, { timeout: 3000 })).toBeInTheDocument();
    const other = new BroadcastChannel("codecoach-records");
    const before = db.listGets;
    elsewhere({ title: "Bea's change", revision: 2 });
    other.postMessage({ v: 1, account: "someone-else", type: "story", id: "s1", change: "saved", revision: 2 });
    other.postMessage({ hello: "world" });
    await act(() => new Promise((r) => setTimeout(r, 60)));
    expect(db.listGets).toBe(before); // nothing fetched for those
    other.postMessage({ v: 1, account: nurse.id, type: "story", id: "s1", change: "saved", revision: 2 });
    expect(await screen.findByRole("link", { name: "Bea's change" })).toBeInTheDocument();
    other.close();
  });

  it("a save here tells the other tabs which story changed, and nothing of its content", async () => {
    serve();
    const heard: unknown[] = [];
    const other = new BroadcastChannel("codecoach-records");
    other.onmessage = (e) => heard.push(e.data);
    const { user } = renderApp("/stories/s1", { signedIn: true });
    await user.type(await screen.findByLabelText("Title", undefined, { timeout: 3000 }), " (night shift)");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(heard).toEqual([{ v: 1, account: nurse.id, type: "story", id: "s1", change: "saved", revision: 2 }]));
    expect(JSON.stringify(heard)).not.toMatch(/night shift|Two call lights/);
    other.close();
  });

  it("a clean search shows the new title, keeping the old result on screen until the new answer arrives", async () => {
    serve();
    let searches = 0;
    server.use(http.post(`${API}/api/v1/me/search`, async () => {
      searches += 1;
      if (searches > 1) await delay(150);
      const s = db.current!;
      return HttpResponse.json({
        items: [{ type: "story", id: s.id, parent_id: null, title: s.title, snippet: null, matched: ["title"], state: null, detail: null, tags: [], at: s.updated_at }],
        words: ["call"], capped: [], unavailable: [], counts: { notes: 0, stories: 1, kits: 0, applications: 0 },
      });
    }));
    const { user } = renderApp("/search", { signedIn: true });
    await user.type(await screen.findByLabelText("Words to find", undefined, { timeout: 3000 }), "call");
    const results = screen.getByRole("region", { name: "Results" });
    expect(await within(results).findByRole("link", { name: /Two call lights/ })).toBeInTheDocument();
    elsewhere({ title: "Two call lights at once", revision: 2 });
    const other = new BroadcastChannel("codecoach-records");
    other.postMessage({ v: 1, account: nurse.id, type: "story", id: "s1", change: "saved", revision: 2 });
    await waitFor(() => expect(searches).toBe(2));
    expect(within(results).getAllByRole("link")).toHaveLength(1); // still showing while it's asked again
    expect(await within(results).findByRole("link", { name: /Two call lights at once/ })).toBeInTheDocument();
    other.close();
  });

  it("counts are asked again for a deletion, not for an archive", async () => {
    serve();
    let summaries = 0;
    server.use(
      http.get(`${API}/api/v1/me/data-summary`, () => {
        summaries += 1;
        return HttpResponse.json({ categories: [{ key: "stories", group: "work", label: "Stories, with their earlier versions", count: db.current ? 1 : 0, note: null }] });
      }),
      http.get(`${API}/api/v1/ai/usage`, () => HttpResponse.json({ used_today: 0, daily_limit: 50, remaining_today: 50, provider: "offline" })),
      http.get(`${API}/api/v1/interviews`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 })),
    );
    renderApp("/settings/data", { signedIn: true });
    expect(await screen.findByText("Stories, with their earlier versions", { exact: false }, { timeout: 3000 })).toHaveTextContent("1 Stories");
    const other = new BroadcastChannel("codecoach-records");
    other.postMessage({ v: 1, account: nurse.id, type: "story", id: "s1", change: "archived", revision: 1 });
    await act(() => new Promise((r) => setTimeout(r, 60)));
    expect(summaries).toBe(1); // archived stories are still counted
    db.current = null;
    other.postMessage({ v: 1, account: nurse.id, type: "story", id: "s1", change: "deleted" });
    expect(await screen.findByText(/Nothing yet: Stories, with their earlier versions/)).toBeInTheDocument();
    expect(summaries).toBe(2);
    other.close();
  });

  it("the tab that saved doesn't act on its own hint", async () => {
    serve();
    const heard: unknown[] = [];
    const other = new BroadcastChannel("codecoach-records");
    other.onmessage = (e) => heard.push(e.data);
    const { user } = renderApp("/stories/s1", { signedIn: true });
    await user.type(await screen.findByLabelText("Title", undefined, { timeout: 3000 }), " (night shift)");
    const gets = db.gets;
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(heard).toHaveLength(1)); // the hint went out
    await act(() => new Promise((r) => setTimeout(r, 60)));
    expect(db.gets).toBe(gets); // and this tab didn't fetch the story it just saved
    other.close();
  });
});
