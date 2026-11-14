/**
 * An application's private notes are revision-checked (Volume 8, prompt 5): two devices editing
 * them from the same start never silently lose one version. Unrelated edits don't send the notes;
 * a stale notes save shows both versions; a restored local draft from an older base is compared,
 * not saved over the newer one; and another account never sees this account's draft.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Application } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const ada = { ...baseUser, career_track: "registered-nurse" };
const asUser = (u = ada) => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: u }))));
const now = () => new Date().toISOString();
const draftKey = (userId: string) => `codecoach.appnotes.v1.${userId}.a1`;

function app(over: Partial<Application> = {}): Application {
  return {
    id: "a1", employer: "Mercy General", role_title: "Ward nurse", stage: "applied", applied_on: null, next_action: "Call the recruiter",
    next_action_due: null, target: null, archived: false, next_event: null, updated_at: now(), link: null, notes: "Recruiter: Sam",
    notes_revision: 1, stories: [], events: [], history: [], created_at: now(), ...over,
  };
}

/** The server's rule for the notes: a change must name the revision it started from. */
function fakeApp(start: Application) {
  const state = { current: start, patches: [] as Record<string, unknown>[] };
  server.use(
    http.get(`${API}/api/v1/me/applications/:id`, () => HttpResponse.json(state.current)),
    http.patch(`${API}/api/v1/me/applications/:id`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      state.patches.push(body);
      let next = { ...state.current, next_action: (body.next_action as string) ?? state.current.next_action };
      if (typeof body.notes === "string" && body.notes !== state.current.notes) {
        if (body.notes_expected_revision !== state.current.notes_revision) {
          return HttpResponse.json({ error: { code: "notes_conflict", message: "Changed elsewhere", request_id: "r",
            details: { current_revision: state.current.notes_revision, current: state.current.notes } } }, { status: 409 });
        }
        next = { ...next, notes: body.notes, notes_revision: state.current.notes_revision + 1 };
      }
      state.current = next;
      return HttpResponse.json(state.current);
    }),
  );
  return state;
}

afterEach(() => localStorage.clear());

it("a stale notes save shows both versions; nothing is overwritten until the learner chooses", async () => {
  asUser();
  const fake = fakeApp(app());
  const { user } = renderApp("/applications/a1", { signedIn: true });
  const notes = await screen.findByLabelText(/Notes \(private\)/);
  // Another device saves first.
  fake.current = { ...fake.current, notes: "Recruiter: Sam. Panel on Tuesday.", notes_revision: 2 };
  await user.clear(notes);
  await user.type(notes, "Recruiter: Sam. Bring references.");
  await user.click(screen.getByRole("button", { name: "Save details" }));
  const conflict = await screen.findByRole("region", { name: "Edit conflict" });
  expect(within(conflict).getByText("Recruiter: Sam. Panel on Tuesday.")).toBeInTheDocument();
  expect(within(conflict).getByText("Recruiter: Sam. Bring references.")).toBeInTheDocument();
  expect(fake.current.notes).toBe("Recruiter: Sam. Panel on Tuesday."); // nothing overwritten
  expect(notes).toHaveValue("Recruiter: Sam. Bring references."); // the page's text kept
  await user.click(within(conflict).getByRole("button", { name: /Keep my notes/ }));
  await waitFor(() => expect(fake.current.notes).toBe("Recruiter: Sam. Bring references."));
  expect(fake.patches.at(-1)!.notes_expected_revision).toBe(2); // deliberately over the version seen
  expect(screen.queryByRole("region", { name: "Edit conflict" })).not.toBeInTheDocument();
});

it("editing the next action doesn't send the notes, so it can't conflict with them", async () => {
  asUser();
  const fake = fakeApp(app());
  const { user } = renderApp("/applications/a1", { signedIn: true });
  const next = await screen.findByLabelText("Next action");
  fake.current = { ...fake.current, notes: "Changed on the phone", notes_revision: 2 };
  await user.clear(next);
  await user.type(next, "Send thank-you email");
  await user.click(screen.getByRole("button", { name: "Save details" }));
  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  expect(fake.patches[0]).not.toHaveProperty("notes");
  expect(fake.current.notes).toBe("Changed on the phone");
});

it("unsaved notes are kept in this browser; restoring an older one is compared, not saved over the newer", async () => {
  asUser();
  const fake = fakeApp(app());
  const first = renderApp("/applications/a1", { signedIn: true });
  const notes = await screen.findByLabelText(/Notes \(private\)/);
  await first.user.type(notes, " Ask about parking.");
  expect(JSON.parse(localStorage.getItem(draftKey(ada.id))!)).toEqual({ notes: "Recruiter: Sam Ask about parking.", base: 1 });
  first.unmount(); // closed without saving
  fake.current = { ...fake.current, notes: "Saved on the phone meanwhile", notes_revision: 2 };
  const again = renderApp("/applications/a1", { signedIn: true });
  const offer = await screen.findByRole("region", { name: "Unsaved notes found" });
  await again.user.click(within(offer).getByRole("button", { name: "Restore them" }));
  const conflict = await screen.findByRole("region", { name: "Edit conflict" });
  expect(within(conflict).getByText("Saved on the phone meanwhile")).toBeInTheDocument();
  expect(screen.getByLabelText(/Notes \(private\)/)).toHaveValue("Recruiter: Sam Ask about parking.");
  expect(fake.patches).toHaveLength(0); // nothing sent until the learner chooses
});

it("another account on this browser never sees this account's unsaved notes", async () => {
  asUser();
  fakeApp(app());
  const first = renderApp("/applications/a1", { signedIn: true });
  await first.user.type(await screen.findByLabelText(/Notes \(private\)/), " Ada's private draft");
  first.unmount(); // left unsaved; another person signs in on this browser
  const bea = { ...ada, id: "user-bea", email: "bea@example.com" };
  asUser(bea);
  renderApp("/applications/a1", { signedIn: true });
  await screen.findByLabelText(/Notes \(private\)/);
  expect(screen.queryByRole("region", { name: "Unsaved notes found" })).not.toBeInTheDocument();
  expect(screen.queryByText(/Ada's private draft/)).not.toBeInTheDocument();
});

it("says when this browser can't keep unsaved notes", async () => {
  asUser();
  fakeApp(app());
  const { user } = renderApp("/applications/a1", { signedIn: true });
  const notes = await screen.findByLabelText(/Notes \(private\)/);
  const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
  await user.type(notes, "!");
  expect(await screen.findByText(/This browser can't keep a copy of unsaved notes/)).toBeInTheDocument();
  spy.mockRestore();
});
