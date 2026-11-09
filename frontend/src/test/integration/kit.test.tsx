import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Kit } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const asUser = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: "registered-nurse" } }))));
const URL = "/applications/a1/events/e1/kit";

function kit(over: Partial<Kit> = {}): Kit {
  return {
    event_id: "e1", application_id: "a1", role_title: "Ward nurse", employer: "Mercy General", event_title: "Panel interview", event_kind: "interview",
    on_date: "2026-11-12", local_time: "10:00", timezone: "Europe/London", starts_at: "2026-11-12T10:00:00Z", format: "remote", location: "",
    meeting_link: "https://meet.example.com/secret", interviewers: [{ name: "Ms Lee", role: "Ward manager" }], notes: "Ask about parking.",
    checklist: [
      { id: "s-0", text: "Confirm the date, time and time zone", origin: "suggested", done: false, hidden: false },
      { id: "s-1", text: "Check your microphone and camera", origin: "suggested", done: false, hidden: false },
    ],
    questions: [
      { id: "s-q0", text: "What would you want the person in this role to achieve in the first three months?", group: "role", origin: "suggested", excluded: false, note: null },
      { id: "s-q2", text: "What training or onboarding is there for someone new?", group: "training", origin: "suggested", excluded: false, note: "The job description mentions “induction”: check whether it already answers this." },
    ],
    stories: [], target_title: null, saved: false, revision: 0, rescheduled_from: null, missing_stories: 0, ...over,
  };
}

describe("the interview-day kit", () => {
  it("labels suggestions, says a tick is only yours, and saves the order and choices you make", async () => {
    asUser();
    let body: Record<string, unknown> | null = null;
    server.use(
      http.get(`${API}/api/v1/me/applications/a1/events/e1/kit`, () => HttpResponse.json(kit())),
      http.put(`${API}/api/v1/me/applications/a1/events/e1/kit`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(kit({ ...(body as Partial<Kit>), saved: true, stories: [] }));
      }),
    );
    const { user } = renderApp(URL, { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Panel interview" })).toBeInTheDocument();
    expect(screen.getAllByText("Suggested").length).toBeGreaterThan(0);
    expect(screen.getByText(/CodeCoach doesn't check your camera, connection, documents or travel/)).toBeInTheDocument();
    expect(screen.getByText(/mentions “induction”/)).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Confirm the date, time and time zone" }));
    await user.click(screen.getByRole("button", { name: /Move “What training or onboarding.*” up/ }));
    const second = screen.getAllByRole("checkbox", { name: "Ask this" })[1]!;
    await user.click(second);
    await user.type(screen.getByLabelText("Add your own question"), "How is feedback given to new nurses?");
    await user.click(screen.getAllByRole("button", { name: "Add" })[1]!);
    await user.click(screen.getByRole("button", { name: "Save kit" }));
    await waitFor(() => expect(body).not.toBeNull());
    const b = body as unknown as { checklist: { done: boolean }[]; questions: { id: string; excluded: boolean; origin: string }[] };
    expect(b.checklist[0]!.done).toBe(true);
    expect(b.questions.map((q) => q.id).slice(0, 2)).toEqual(["s-q2", "s-q0"]);
    expect(b.questions[1]!.excluded).toBe(true);
    expect(b.questions[2]!.origin).toBe("yours");
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("keeps private details out of the printout until chosen, and the preview is what prints", async () => {
    asUser();
    server.use(http.get(`${API}/api/v1/me/applications/a1/events/e1/kit`, () => HttpResponse.json(kit({ saved: true }))));
    const { user } = renderApp(URL, { signedIn: true });
    const pack = await screen.findByRole("article", { name: "Your interview pack" });
    expect(within(pack).getByText(/Not sent to anyone/)).toBeInTheDocument();
    expect(within(pack).queryByText(/meet\.example\.com/)).toBeNull();
    expect(within(pack).queryByText(/Ms Lee/)).toBeNull();
    expect(within(pack).queryByText(/Ask about parking/)).toBeNull();
    expect(within(pack).getByText(/What training or onboarding/)).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Meeting link (private)" }));
    await user.click(screen.getByRole("checkbox", { name: "Your notes (private)" }));
    expect(within(pack).getByText(/meet\.example\.com\/secret/)).toBeInTheDocument();
    expect(within(pack).getByText("Ask about parking.")).toBeInTheDocument();
    const printSpy = vi.spyOn(window, "print").mockImplementation(() => {});
    await user.click(screen.getByRole("button", { name: "Print…" }));
    expect(printSpy).toHaveBeenCalled();
  });

  it("is the same generic answer for someone else's interview", async () => {
    asUser();
    server.use(http.get(`${API}/api/v1/me/applications/a1/events/e1/kit`, () => HttpResponse.json({ error: { code: "not_found", message: "Interview not found", request_id: "r" } }, { status: 404 })));
    renderApp(URL, { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "This interview kit isn't available" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Your applications" })).toHaveAttribute("href", "/applications");
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });
});

describe("the kit stays truthful when things change", () => {
  const KIT = `${API}/api/v1/me/applications/a1/events/e1/kit`;
  const story = (over: Partial<Kit["stories"][number]> = {}) =>
    ({ id: "st1", title: "Two call lights", short_version: "I triaged by risk.", archived: false, revision: 1, chosen_revision: 1, ...over });

  it("a stale save keeps your edits and offers to save over it or load the saved kit", async () => {
    asUser();
    const bodies: Record<string, unknown>[] = [];
    let current = kit({ saved: true, revision: 3, notes: "From the other tab" });
    server.use(
      http.get(KIT, () => HttpResponse.json(current)),
      http.put(KIT, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        bodies.push(body);
        if (body.expected_revision !== current.revision) {
          return HttpResponse.json({ error: { code: "stale_revision", message: "This kit was saved somewhere else", request_id: "r", details: { current_revision: current.revision, current } } }, { status: 409 });
        }
        current = kit({ ...(body as Partial<Kit>), saved: true, revision: current.revision + 1 });
        return HttpResponse.json(current);
      }),
    );
    // This page loaded revision 2; another tab has since saved revision 3.
    server.use(http.get(KIT, () => HttpResponse.json(kit({ saved: true, revision: 2, notes: "Old" })), { once: true }));
    const { user } = renderApp(URL, { signedIn: true });
    const notes = await screen.findByLabelText("Private notes");
    await user.clear(notes);
    await user.type(notes, "Mine");
    await user.click(screen.getByRole("button", { name: "Save kit" }));
    const conflict = await screen.findByRole("region", { name: "Edit conflict" });
    expect(within(conflict).getByRole("alert")).toHaveTextContent("This kit was saved in another tab or on another device (version 3)");
    // Both versions of what differs: this page's notes and the other tab's.
    expect(within(conflict).getByText("Mine")).toBeInTheDocument();
    expect(within(conflict).getByText("From the other tab")).toBeInTheDocument();
    expect(screen.getByLabelText("Private notes")).toHaveValue("Mine"); // nothing lost
    expect(bodies[0]!.expected_revision).toBe(2);
    await user.click(within(conflict).getByRole("button", { name: "Keep mine (replaces that version)" }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toMatchObject({ expected_revision: 3, notes: "Mine" }); // an explicit choice, against what's there now
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Edit conflict" })).toBeNull();
  });

  it("discarding your edits loads the saved kit instead", async () => {
    asUser();
    server.use(
      http.get(KIT, () => HttpResponse.json(kit({ saved: true, revision: 3, notes: "From the other tab" }))),
      http.put(KIT, () => HttpResponse.json({ error: { code: "stale_revision", message: "x", request_id: "r",
        details: { current_revision: 3, current: kit({ saved: true, revision: 3, notes: "From the other tab" }) } } }, { status: 409 })),
    );
    server.use(http.get(KIT, () => HttpResponse.json(kit({ saved: true, revision: 2, notes: "Old" })), { once: true }));
    const { user } = renderApp(URL, { signedIn: true });
    const notes = await screen.findByLabelText("Private notes");
    await user.type(notes, " and mine");
    await user.click(screen.getByRole("button", { name: "Save kit" }));
    await user.click(within(await screen.findByRole("region", { name: "Edit conflict" })).getByRole("button", { name: "Use the saved version" }));
    await waitFor(() => expect(screen.getByLabelText("Private notes")).toHaveValue("From the other tab"));
    expect(screen.getByText(/Your unsaved changes were discarded/)).toBeInTheDocument();
  });

  it("says when the interview moved since the kit was saved, without unticking anything", async () => {
    asUser();
    server.use(http.get(KIT, () => HttpResponse.json(kit({
      saved: true, revision: 1, on_date: "2026-11-13", local_time: "14:30",
      rescheduled_from: { on_date: "2026-11-12", local_time: "10:00", timezone: "Europe/London" },
      checklist: [{ id: "s-0", text: "Confirm the date, time and time zone", origin: "suggested", done: true, hidden: false }],
    }))));
    renderApp(URL, { signedIn: true });
    expect(await screen.findByText(/This interview moved since you last saved the kit/)).toHaveTextContent(/10:00.*now.*14:30/);
    expect(screen.getByRole("checkbox", { name: "Confirm the date, time and time zone" })).toBeChecked();
  });

  it("flags an example edited after it was chosen, and saving after rereading records it", async () => {
    asUser();
    let body: Record<string, unknown> | null = null;
    server.use(
      http.get(KIT, () => HttpResponse.json(kit({ saved: true, revision: 1, stories: [story({ revision: 3, chosen_revision: 1 }), story({ id: "st2", title: "Night handover", archived: true })], missing_stories: 1 }))),
      http.get(`${API}/api/v1/me/stories`, () => HttpResponse.json([{ id: "st1", title: "Two call lights" }])),
      http.put(KIT, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(kit({ saved: true, revision: 2, stories: [story({ revision: 3, chosen_revision: 3 })] }));
      }),
    );
    const { user } = renderApp(URL, { signedIn: true });
    const changes = await screen.findByRole("list", { name: "Examples edited since you chose them" });
    expect(changes).toHaveTextContent("“Two call lights” was edited after you chose it (version 1 then, 3 now).");
    expect(within(changes).getByRole("link", { name: "Read it" })).toHaveAttribute("href", "/stories/st1");
    expect(screen.getByText(/An example you chose was deleted/)).toBeInTheDocument();
    // An archived example stays tickable, so it can be removed from the kit.
    expect(screen.getByRole("checkbox", { name: "Night handover (archived)" })).toBeChecked();
    await user.click(within(changes).getByRole("button", { name: "I've reread it" }));
    await user.click(screen.getByRole("button", { name: "Save kit" }));
    await waitFor(() => expect(body).toMatchObject({ reviewed_story_ids: ["st1"], expected_revision: 1 }));
    await waitFor(() => expect(screen.queryByRole("list", { name: "Examples edited since you chose them" })).toBeNull());
  });

  it("with unsaved changes the printout is only a notice, never the unsaved kit", async () => {
    asUser();
    server.use(http.get(KIT, () => HttpResponse.json(kit({ saved: true, revision: 1 }))));
    const { user } = renderApp(URL, { signedIn: true });
    const pack = await screen.findByRole("article", { name: "Your interview pack" });
    expect(within(pack).queryByText(/unsaved changes/)).toBeNull();
    await user.type(screen.getByLabelText("Private notes"), " more");
    expect(pack).toHaveClass("print-pack--unsaved");
    expect(within(pack).getByText(/This kit has unsaved changes, so it isn't printed/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Print…" })).toBeDisabled();
  });
});

describe("exact save state on the kit", () => {
  const KIT = `${API}/api/v1/me/applications/a1/events/e1/kit`;

  it("edits made while a save is on its way stay, and aren't called saved", async () => {
    asUser();
    let release!: () => void;
    const answered = new Promise<void>((r) => { release = r; });
    let current = kit({ saved: true, revision: 1, notes: "Old" });
    server.use(
      http.get(KIT, () => HttpResponse.json(current)),
      http.put(KIT, async ({ request }) => {
        const body = (await request.json()) as Partial<Kit>;
        await answered;
        current = kit({ ...body, saved: true, revision: current.revision + 1 });
        return HttpResponse.json(current);
      }),
    );
    const { user } = renderApp(URL, { signedIn: true });
    const notes = await screen.findByLabelText("Private notes");
    await user.clear(notes);
    await user.type(notes, "First");
    await user.click(screen.getByRole("button", { name: "Save kit" }));
    await user.type(notes, " and more"); // typed while saving
    release();
    await waitFor(() => expect(screen.getByText("Unsaved changes")).toBeInTheDocument());
    expect(screen.getByLabelText("Private notes")).toHaveValue("First and more");
    expect(screen.queryByText("Saved.")).toBeNull();
  });

  it("in-app navigation asks before leaving unsaved kit edits, which live only on this page", async () => {
    asUser();
    server.use(http.get(KIT, () => HttpResponse.json(kit({ saved: true, revision: 1, notes: "Old" }))));
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { user } = renderApp(URL, { signedIn: true });
    const notes = await screen.findByLabelText("Private notes");
    await user.type(notes, " and mine");
    await user.click(screen.getByRole("link", { name: "Back to the application" }));
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/changes that aren't saved yet/));
    expect(screen.getByLabelText("Private notes")).toHaveValue("Old and mine"); // stayed on the page
    confirm.mockRestore();
  });
});
