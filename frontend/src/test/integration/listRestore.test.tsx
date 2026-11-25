/**
 * Coming back to a list that changed (Volume 9, prompt 6; NAVIGATION.md "Coming back to a list
 * that changed"): the decisions, on the notebook. The item opened is found again by its link; if
 * it's gone, its nearest neighbour gets focus and a screen reader hears why; with nothing left,
 * the page's main region does; a learner who took over while the list loaded is left alone; an
 * account signing out takes this tab's list memory with it. Real scrolling is checked in the
 * browser (e2e/list-restore.spec.ts): jsdom lays nothing out.
 */
import { act, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { clearLocalWork } from "@/auth/localWork";
import { ITEM_GONE } from "@/hooks/useScrollMemory";

import { tokenResponse, user as baseUser } from "../fixtures";
import { makeNote, noteStore } from "../notes";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const announced = () => document.getElementById("app-announcer")?.textContent ?? "";
const focusedHref = () => document.activeElement?.getAttribute("href") ?? null;

beforeEach(() => {
  // jsdom lays nothing out; a row with no box counts as hidden, and hidden rows are never focused.
  vi.spyOn(Element.prototype, "getClientRects").mockReturnValue([{}] as unknown as DOMRectList);
  document.getElementById("app-announcer")?.remove();
});
afterEach(() => vi.restoreAllMocks());

async function openAndReturn(title: string, whileAway: () => void) {
  const { user, router } = renderApp("/notes", { signedIn: true });
  await user.click(await screen.findByRole("link", { name: title }));
  await waitFor(() => expect(router.state.location.pathname).not.toBe("/notes"));
  whileAway();
  await act(() => router.navigate(-1));
  return { user, router };
}

it("the note opened is focused again when it's still there", async () => {
  asNurse();
  noteStore.notes.push(makeNote({ title: "Alpha" }), makeNote({ title: "Bravo" }), makeNote({ title: "Charlie" }));
  await openAndReturn("Bravo", () => noteStore.notes.unshift(makeNote({ title: "Added while away" })));
  await waitFor(() => expect(focusedHref()).toBe("/notes/n-2"));
  expect(announced()).toBe("");
});

it("a note deleted while away: its nearest neighbour is focused, and a screen reader hears that it's gone", async () => {
  asNurse();
  noteStore.notes.push(makeNote({ title: "Alpha" }), makeNote({ title: "Bravo" }), makeNote({ title: "Charlie" }));
  await openAndReturn("Bravo", () => { noteStore.notes = noteStore.notes.filter((n) => n.title !== "Bravo"); });
  await waitFor(() => expect(["/notes/n-1", "/notes/n-3"]).toContain(focusedHref()));
  await waitFor(() => expect(announced()).toBe(ITEM_GONE));
  expect(screen.queryByRole("link", { name: "Bravo" })).not.toBeInTheDocument(); // not pretended to exist
});

it("nothing left in the list: focus goes to the page's main region, with the same announcement", async () => {
  asNurse();
  noteStore.notes.push(makeNote({ title: "Only one" }));
  await openAndReturn("Only one", () => { noteStore.notes = []; });
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("main")));
  await waitFor(() => expect(announced()).toBe(ITEM_GONE));
});

it("a learner who scrolls while the list is reloading is left alone", async () => {
  asNurse();
  noteStore.notes.push(makeNote({ title: "Alpha" }), makeNote({ title: "Bravo" }));
  let release!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  let hold = false;
  // Holds the list's reload, then lets the shared notes handler answer.
  server.use(http.get(`${API}/api/v1/me/notes`, async () => { if (hold) await held; }));
  await openAndReturn("Bravo", () => { hold = true; });
  window.dispatchEvent(new WheelEvent("wheel", { deltaY: 120 }));
  release();
  expect(await screen.findByRole("link", { name: "Bravo" })).toBeInTheDocument();
  await new Promise((resolve) => setTimeout(resolve, 100)); // a restore would have happened by now
  expect(focusedHref()).toBeNull();
});

it("signing out here takes this tab's list memory with it; nothing else in this tab's storage", () => {
  sessionStorage.setItem("scroll:abc", "1200");
  sessionStorage.setItem("focus:scroll:abc", JSON.stringify({ href: "/notes/n-9", next: null, prev: null, top: 300 }));
  sessionStorage.setItem("codecoach.other", "kept");
  clearLocalWork("user-1");
  expect(sessionStorage.getItem("scroll:abc")).toBeNull();
  expect(sessionStorage.getItem("focus:scroll:abc")).toBeNull();
  expect(sessionStorage.getItem("codecoach.other")).toBe("kept");
});
