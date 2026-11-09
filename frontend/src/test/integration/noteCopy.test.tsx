/**
 * Keep both after a note conflict makes one copy (Volume 8, prompt 4): the text chosen is captured
 * when the button is pressed and the decision gets one key, kept in this browser. A double click,
 * a lost reply, a retry or a reload never makes a second copy; a copy made and then deleted isn't
 * made again by a retry; a deliberate new copy is still possible; the source note is untouched.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { tokenResponse, user as baseUser } from "../fixtures";
import { makeNote, noteStore } from "../notes";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const posts = () => noteStore.bodies.filter((b) => b.copy_of);

async function conflictOn(body = "v1") {
  asNurse();
  const note = makeNote({ title: "Plan", body });
  noteStore.notes.push(note);
  const app = renderApp(`/notes/${note.id}`, { signedIn: true });
  const editor = await screen.findByLabelText("Note");
  Object.assign(noteStore.notes[0]!, { body: "theirs", revision: 2 }); // another tab saves first
  await app.user.type(editor, " mine");
  const panel = await screen.findByRole("region", { name: "Edit conflict" }, { timeout: 3000 });
  return { ...app, note, panel, editor };
}

afterEach(() => localStorage.clear());

it("a double click makes one copy of exactly what was shown, and the source is untouched", async () => {
  const { user, panel, note } = await conflictOn();
  const keep = within(panel).getByRole("button", { name: "Keep both" });
  await user.dblClick(keep);
  expect(await screen.findByText(/Your version was saved as a separate note/)).toBeInTheDocument();
  const made = noteStore.notes.filter((n) => n.body === "v1 mine");
  expect(made).toHaveLength(1);
  expect(made[0]!.title).toBe("Plan (my version)");
  expect(new Set(posts().map((b) => b.client_request_id)).size).toBe(1);
  expect(posts().every((b) => b.copy_of === note.id)).toBe(true);
  expect(noteStore.notes.find((n) => n.id === note.id)!.body).toBe("theirs"); // the source as saved
  expect(screen.getByLabelText("Note")).toHaveValue("theirs"); // this note back to the saved version
  expect(document.activeElement).toHaveTextContent(/saved as a separate note/); // focus lands on the result
});

it("a lost reply offers Check copy and Retry same copy; retrying makes nothing twice", async () => {
  const { user, panel } = await conflictOn();
  noteStore.dropNextCreateReply = true;
  await user.click(within(panel).getByRole("button", { name: "Keep both" }));
  expect(await within(panel).findByText(/We couldn't confirm the copy of your version/)).toBeInTheDocument();
  expect(within(panel).queryByRole("button", { name: "Keep both" })).not.toBeInTheDocument(); // no unqualified create
  expect(within(panel).getByRole("button", { name: "Copy my text" })).toBeInTheDocument(); // still available
  await user.click(within(panel).getByRole("button", { name: "Retry same copy" }));
  expect(await screen.findByText(/Your version was saved as a separate note/)).toBeInTheDocument();
  expect(noteStore.notes.filter((n) => n.body === "v1 mine")).toHaveLength(1);
  const keys = posts().map((b) => b.client_request_id);
  expect(keys).toHaveLength(2);
  expect(keys[1]).toBe(keys[0]);
});

it("Check copy finds a copy that arrived, without sending it again", async () => {
  const { user, panel } = await conflictOn();
  noteStore.dropNextCreateReply = true;
  await user.click(within(panel).getByRole("button", { name: "Keep both" }));
  await within(panel).findByText(/We couldn't confirm the copy/);
  server.use(http.get(`${API}/api/v1/me/requests/:key`, ({ params }) => {
    const id = noteStore.keys.get(params.key as string);
    return id ? HttpResponse.json({ kind: "note", state: "done", id, created_at: new Date().toISOString() })
      : HttpResponse.json({ error: { code: "request_not_found", message: "no record", request_id: "r" } }, { status: 404 });
  }));
  await user.click(within(panel).getByRole("button", { name: "Check copy" }));
  const result = await screen.findByText(/Your version was saved as a separate note/);
  const made = noteStore.notes.find((n) => n.body === "v1 mine")!;
  expect(within(result).getByRole("link")).toHaveAttribute("href", `/notes/${made.id}`);
  expect(posts()).toHaveLength(1); // checked, not sent again
});

it("a copy made and then deleted isn't made again by a retry; a new copy is a deliberate choice", async () => {
  const { user, panel } = await conflictOn();
  noteStore.dropNextCreateReply = true;
  await user.click(within(panel).getByRole("button", { name: "Keep both" }));
  await within(panel).findByText(/We couldn't confirm the copy/);
  const made = noteStore.notes.find((n) => n.body === "v1 mine")!;
  noteStore.notes = noteStore.notes.filter((n) => n.id !== made.id); // deleted in another tab
  await user.click(within(panel).getByRole("button", { name: "Retry same copy" }));
  expect(await within(panel).findByText(/That copy was made, then deleted/)).toBeInTheDocument();
  expect(noteStore.notes.filter((n) => n.body === "v1 mine")).toHaveLength(0);
  expect(screen.getByLabelText("Note")).toHaveValue("v1 mine"); // the local version is still here
  await user.click(within(panel).getByRole("button", { name: "Make a new copy" }));
  expect(await screen.findByText(/Your version was saved as a separate note/)).toBeInTheDocument();
  const keys = posts().map((b) => b.client_request_id);
  expect(keys[2]).not.toBe(keys[0]); // a new decision, a new key
  expect(noteStore.notes.filter((n) => n.body === "v1 mine")).toHaveLength(1);
});

it("text typed after Keep both isn't in the copy, and stays on the page", async () => {
  const { user, panel, editor } = await conflictOn();
  noteStore.dropNextCreateReply = true;
  await user.click(within(panel).getByRole("button", { name: "Keep both" }));
  await within(panel).findByText(/We couldn't confirm the copy/);
  await user.type(editor, " and more");
  await user.click(within(panel).getByRole("button", { name: "Retry same copy" }));
  expect(await screen.findByText(/What you typed after choosing Keep both isn't in it/)).toBeInTheDocument();
  expect(noteStore.notes.find((n) => n.title === "Plan (my version)")!.body).toBe("v1 mine"); // the snapshot
  expect(screen.getByLabelText("Note")).toHaveValue("v1 mine and more");
  expect(screen.getByRole("region", { name: "Edit conflict" })).toBeInTheDocument(); // still to resolve
});

it("after a reload, a copy whose reply was lost is checked, never sent again", async () => {
  const first = await conflictOn();
  noteStore.dropNextCreateReply = true;
  await first.user.click(within(first.panel).getByRole("button", { name: "Keep both" }));
  await within(first.panel).findByText(/We couldn't confirm the copy/);
  const key = posts()[0]!.client_request_id as string;
  expect(localStorage.getItem(`codecoach.pending.v1.${nurse.id}`)).toContain(key); // kept across a reload
  first.unmount();
  server.use(http.get(`${API}/api/v1/me/requests/:key`, ({ params }) => HttpResponse.json({
    kind: "note", state: "done", id: noteStore.keys.get(params.key as string), created_at: new Date().toISOString(),
  })));
  renderApp(`/notes/${first.note.id}`, { signedIn: true });
  expect(await screen.findByText(/Your copy of your version from .* arrived\./)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open the copy" })).toHaveAttribute("href", `/notes/${noteStore.keys.get(key)}`);
  await waitFor(() => expect(localStorage.getItem(`codecoach.pending.v1.${nurse.id}`) ?? "").not.toContain(key));
  expect(posts()).toHaveLength(1);
});
