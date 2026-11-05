import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { tokenResponse, user as baseUser } from "../fixtures";
import { makeNote, noteStore } from "../notes";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));

describe("Notebook", () => {
  it("captures a note from a question with a snapshot, autosaving once and then updating", async () => {
    asNurse();
    const { user } = renderApp("/careers/registered-nurse/questions/e-time-0", { signedIn: true });
    const panel = await screen.findByRole("region", { name: "Notes" });
    await user.click(within(panel).getByRole("button", { name: "Add a note" }));
    expect(within(panel).getByLabelText(/Include a snapshot of the question/)).toBeChecked();
    expect(within(panel).getByText("Not saved yet: start typing")).toBeInTheDocument();
    expect(within(panel).queryByRole("status")).toBeNull(); // the save state changes as you type: not a live region
    await user.type(within(panel).getByLabelText("Title"), "Escalate early");
    await waitFor(() => expect(within(panel).getByText("Saved", { exact: true })).toBeInTheDocument(), { timeout: 3000 });
    await user.type(within(panel).getByLabelText("Tags (comma-separated)"), "sbar, escalation");
    await waitFor(() => expect(noteStore.notes[0]!.tags).toEqual(["sbar", "escalation"]), { timeout: 3000 });
    expect(noteStore.requests.filter((r) => r === "POST")).toHaveLength(1); // created once, then updated
    const n = noteStore.notes[0]!;
    expect(n.title).toBe("Escalate early");
    expect(n.excerpt).toBe("Tell me about a time patient assessment was an important part of your work.");
    expect(n.source).toMatchObject({ type: "question", id: "e-time-0" });
    expect(within(panel).getByRole("link", { name: "Open in your notebook" })).toHaveAttribute("href", `/notes/${n.id}`);
  });

  it("says when a save fails, keeps the text, retries, and recovers an unsaved draft after a reload", async () => {
    asNurse();
    const note = makeNote({ title: "Shift notes", body: "start" });
    noteStore.notes.push(note);
    noteStore.failSaves = 1;
    const first = renderApp(`/notes/${note.id}`, { signedIn: true });
    const body = await screen.findByLabelText("Note");
    await first.user.type(body, " more");
    expect(await screen.findByText("Could not save. Your text is kept in this browser.", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(body).toHaveValue("start more");
    await first.user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(noteStore.notes[0]!.body).toBe("start more"));
    await waitFor(() => expect(screen.getByText("Saved", { selector: ".note-status" })).toBeInTheDocument());

    // Now an edit that never reaches the server (failing), then the page is reopened: the draft is offered back.
    noteStore.failSaves = 99;
    await first.user.type(body, "!");
    expect(await screen.findByText("Could not save. Your text is kept in this browser.", {}, { timeout: 3000 })).toBeInTheDocument();
    // Leaving the page tries once more (keepalive); the server is still failing, so the draft stays.
    const before = noteStore.requests.length;
    first.unmount();
    await waitFor(() => expect(noteStore.requests.length).toBeGreaterThan(before));
    await new Promise((r) => setTimeout(r, 50));
    noteStore.failSaves = 0;
    const second = renderApp(`/notes/${note.id}`, { signedIn: true });
    const banner = await screen.findByRole("region", { name: "Unsaved draft found" });
    await second.user.click(within(banner).getByRole("button", { name: "Restore it" }));
    expect(screen.getByLabelText("Note")).toHaveValue("start more!");
    await waitFor(() => expect(noteStore.notes[0]!.body).toBe("start more!"), { timeout: 3000 });
  });

  it("never overwrites newer text from another tab: shows both versions and lets you choose", async () => {
    asNurse();
    const note = makeNote({ title: "Plan", body: "mine v1" });
    noteStore.notes.push(note);
    const { user } = renderApp(`/notes/${note.id}`, { signedIn: true });
    const body = await screen.findByLabelText("Note");
    // Another tab saves first.
    Object.assign(noteStore.notes[0]!, { body: "theirs v2", revision: 2 });
    await user.type(body, " + mine");
    const panel = await screen.findByRole("region", { name: "Edit conflict" }, { timeout: 3000 });
    expect(panel).toHaveTextContent("mine v1 + mine");
    expect(panel).toHaveTextContent("theirs v2");
    expect(noteStore.notes[0]!.body).toBe("theirs v2"); // nothing overwritten
    expect(screen.getByText("Not saved: this note changed somewhere else")).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Keep my version" }));
    await waitFor(() => expect(noteStore.notes[0]!.body).toBe("mine v1 + mine"));
    expect(noteStore.notes[0]!.revision).toBe(3);
  });

  it("can take the saved version or keep both", async () => {
    asNurse();
    const note = makeNote({ title: "Plan", body: "v1" });
    noteStore.notes.push(note);
    const { user } = renderApp(`/notes/${note.id}`, { signedIn: true });
    const body = await screen.findByLabelText("Note");
    Object.assign(noteStore.notes[0]!, { body: "theirs", revision: 2 });
    await user.type(body, " mine");
    const panel = await screen.findByRole("region", { name: "Edit conflict" }, { timeout: 3000 });
    await user.click(within(panel).getByRole("button", { name: "Keep both" }));
    expect(await screen.findByText(/Your version was saved as a separate note/)).toBeInTheDocument();
    expect(noteStore.notes.map((n) => n.body)).toEqual(["v1 mine", "theirs"]);
    expect(screen.getByLabelText("Note")).toHaveValue("theirs");
  });

  it("saves pending text when you navigate away before the autosave fires", async () => {
    asNurse();
    const note = makeNote({ title: "Quick", body: "" });
    noteStore.notes.push(note);
    const { user, router } = renderApp(`/notes/${note.id}`, { signedIn: true });
    await user.type(await screen.findByLabelText("Note"), "typed then left");
    await act(async () => { await router.navigate("/notes"); });
    await waitFor(() => expect(noteStore.notes.find((n) => n.id === note.id)!.body).toBe("typed then left"));
  });

  it("renders Markdown safely: no HTML, no images, no javascript: links", async () => {
    asNurse();
    const note = makeNote({ title: "Evil", body: "**bold** <script>window.hacked=1</script> <img src=x onerror=alert(1)> ![p](http://evil/x.png) [x](javascript:alert(1)) [ok](https://example.com)" });
    noteStore.notes.push(note);
    const { user } = renderApp(`/notes/${note.id}`, { signedIn: true });
    await screen.findByLabelText("Note");
    await user.click(screen.getByRole("button", { name: "Preview" }));
    const preview = document.querySelector(".note-markdown") as HTMLElement;
    expect(within(preview).getByText("bold").tagName).toBe("STRONG");
    expect(preview.querySelector("script, img")).toBeNull();
    expect((window as unknown as { hacked?: number }).hacked).toBeUndefined();
    const links = [...preview.querySelectorAll("a")];
    expect(links.map((a) => a.getAttribute("href"))).not.toContain("javascript:alert(1)");
    expect(within(preview).getByRole("link", { name: "ok" })).toHaveAttribute("rel", "noopener noreferrer nofollow");
  });

  it("searches, filters by tag, pins first, deletes with undo", async () => {
    asNurse();
    noteStore.notes.push(
      makeNote({ title: "Triage order", body: "ABCs first", tags: ["triage"] }),
      makeNote({ title: "Two pointers", body: "sorted arrays", tags: ["arrays"], pinned: true }),
    );
    const { user, router } = renderApp("/notes", { signedIn: true });
    const list = await within(await screen.findByRole("main")).findByRole("list");
    expect(within(list).getAllByRole("listitem")[0]).toHaveTextContent("Two pointers");
    await user.type(screen.getByRole("searchbox", { name: "Search notes" }), "abcs");
    await waitFor(() => expect(within(screen.getByRole("main")).getAllByRole("listitem")).toHaveLength(1));
    expect(router.state.location.search).toContain("q=abcs");
    await user.clear(screen.getByRole("searchbox", { name: "Search notes" }));
    await user.selectOptions(await screen.findByLabelText("Tag"), "arrays");
    await waitFor(() => expect(within(screen.getByRole("main")).getAllByRole("listitem")).toHaveLength(1));
    await user.click(screen.getByRole("link", { name: "Two pointers" }));
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/notes"));
    const undo = await screen.findByText(/Deleted “Two pointers”\. You can undo this for 10 minutes/);
    await user.click(within(undo.parentElement!).getByRole("button", { name: "Undo" }));
    await waitFor(() => expect(noteStore.notes.map((n) => n.title)).toContain("Two pointers"));
  });

  it("suggests key points without changing the note until accepted", async () => {
    asNurse();
    const note = makeNote({ title: "Shift", body: "Next time I should escalate earlier." });
    noteStore.notes.push(note);
    const { user } = renderApp(`/notes/${note.id}`, { signedIn: true });
    const helper = await screen.findByRole("region", { name: "Key points helper" });
    await user.click(within(helper).getByRole("button", { name: "Suggest key points" }));
    expect(await within(helper).findByText("Next time I should escalate earlier.")).toBeInTheDocument();
    expect(noteStore.notes[0]!.key_points).toBeNull();
    await user.click(within(helper).getByRole("button", { name: "Save these key points" }));
    await waitFor(() => expect(noteStore.notes[0]!.key_points).toEqual(["Next time I should escalate earlier."]));
    expect(noteStore.notes[0]!.body).toBe("Next time I should escalate earlier.");
  });

  it("another account's note is simply not found", async () => {
    asNurse();
    renderApp("/notes/someone-elses", { signedIn: true });
    expect(await screen.findByText("Note not found")).toBeInTheDocument();
  });
});
