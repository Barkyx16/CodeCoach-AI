import { createEvent, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Application, ApplicationSummary } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const asUser = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: "registered-nurse" } }))));
const now = () => new Date().toISOString();

function app(over: Partial<Application> = {}): Application {
  return {
    id: "a1", employer: "Mercy General", role_title: "Ward nurse", stage: "applied", applied_on: "2026-10-30", next_action: "Call the recruiter",
    next_action_due: null, target: null, archived: false, next_event: null, updated_at: now(), link: null, notes: "", notes_revision: 1, stories: [], events: [],
    history: [{ from_stage: null, to_stage: "applied", correction: false, note: "", role_title: "Ward nurse", employer: "Mercy General", changed_at: now() }],
    created_at: now(), ...over,
  };
}

function fakeApps(list: Application[]) {
  const store = new Map(list.map((a) => [a.id, a]));
  const sent: { url: string; body: unknown }[] = [];
  server.use(
    http.get(`${API}/api/v1/me/applications`, () => HttpResponse.json([...store.values()] as ApplicationSummary[])),
    http.get(`${API}/api/v1/me/applications/:id`, ({ params }) => HttpResponse.json(store.get(String(params.id)))),
    http.post(`${API}/api/v1/me/applications/:id/stage`, async ({ params, request }) => {
      const body = (await request.json()) as { stage: Application["stage"] };
      sent.push({ url: request.url, body });
      const a = store.get(String(params.id))!;
      const next = { ...a, stage: body.stage };
      store.set(a.id, next);
      return HttpResponse.json(next);
    }),
  );
  return { sent, store };
}

describe("the board", () => {
  it("a card's next interview leads to its kit, and says when the time isn't known", async () => {
    asUser();
    const ev = { id: "e9", kind: "interview" as const, title: "Panel interview", on_date: "2026-11-12", local_time: null, timezone: null, starts_at: null, notes: "", created_at: now() };
    fakeApps([app({ stage: "interviewing", next_event: ev })]);
    renderApp("/applications", { signedIn: true });
    const board = await screen.findByRole("list", { name: "Applications by stage" });
    const card = within(board).getByRole("link", { name: "Ward nurse" }).closest("li")!;
    expect(card).toHaveTextContent(/Next: Panel interview · .*\(time not known\)/);
    expect(within(card).getByRole("link", { name: "Prepare for Panel interview (Mercy General)" })).toHaveAttribute("href", "/applications/a1/events/e9/kit");
  });

  it("moves a card by dragging it or with its keyboard menu: the same change either way", async () => {
    asUser();
    const { sent } = fakeApps([app(), app({ id: "a2", role_title: "Practice nurse", employer: "Hill Clinic", stage: "saved" })]);
    const { user } = renderApp("/applications", { signedIn: true });
    const board = await screen.findByRole("list", { name: "Applications by stage" });
    const interviewing = within(board).getByRole("listitem", { name: /^Interviewing/ });

    // Pointer: drag "Ward nurse" onto Interviewing.
    const card = within(board).getByRole("link", { name: "Ward nurse" }).closest("li")!;
    const data = new Map<string, string>();
    const dataTransfer = { setData: (k: string, v: string) => data.set(k, v), getData: (k: string) => data.get(k) ?? "", effectAllowed: "" };
    fireEvent(card, Object.assign(createEvent.dragStart(card), { dataTransfer }));
    fireEvent(interviewing, Object.assign(createEvent.dragOver(interviewing), { dataTransfer }));
    fireEvent(interviewing, Object.assign(createEvent.drop(interviewing), { dataTransfer }));
    await waitFor(() => expect(sent[0]).toMatchObject({ body: { stage: "interviewing", correction: false } }));
    expect(within(interviewing).getByRole("link", { name: "Ward nurse" })).toBeInTheDocument();

    // Keyboard: the menu on the other card.
    await user.selectOptions(screen.getByLabelText("Move Practice nurse at Hill Clinic to"), "applied");
    await waitFor(() => expect(sent[1]).toMatchObject({ body: { stage: "applied" } }));
  });

  it("keeps a correction ticked while the previous stage change is still saving", async () => {
    asUser();
    const { sent, store } = fakeApps([app()]);
    let release: () => void = () => undefined;
    let held = true;
    server.use(http.post(`${API}/api/v1/me/applications/:id/stage`, async ({ params, request }) => {
      const body = (await request.json()) as { stage: Application["stage"]; correction: boolean };
      sent.push({ url: request.url, body });
      if (held) {
        held = false;
        await new Promise<void>((resolve) => { release = resolve; });
      }
      const a = store.get(String(params.id))!;
      const next = { ...a, stage: body.stage };
      store.set(a.id, next);
      return HttpResponse.json(next);
    }));
    const { user } = renderApp("/applications/a1", { signedIn: true });
    const form = await screen.findByRole("form", { name: "Change the stage" });
    await user.selectOptions(within(form).getByLabelText("Move to"), "offer");
    await user.click(within(form).getByRole("button", { name: "Save stage" }));
    await waitFor(() => expect(sent).toHaveLength(1));
    const tick = within(form).getByRole("checkbox", { name: /This corrects a mistake/ });
    await user.click(tick); // ticked while the first save is still on its way
    release();
    await waitFor(() => expect(within(form).getByRole("button", { name: "Save stage" })).toBeEnabled());
    expect(tick).toBeChecked();
  });

  it("puts a card back and says so when a move can't be saved", async () => {
    asUser();
    fakeApps([app()]);
    server.use(http.post(`${API}/api/v1/me/applications/:id/stage`, () => HttpResponse.json({ error: { code: "internal_error", message: "Something went wrong", request_id: "r" } }, { status: 500 })));
    const { user } = renderApp("/applications", { signedIn: true });
    await user.selectOptions(await screen.findByLabelText("Move Ward nurse at Mercy General to"), "offer");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    const board = screen.getByRole("list", { name: "Applications by stage" });
    expect(within(within(board).getByRole("listitem", { name: /^Applied/ })).getByRole("link", { name: "Ward nurse" })).toBeInTheDocument();
  });

  it("keeps the view, filters and sort in the address", async () => {
    asUser();
    fakeApps([app(), app({ id: "a2", role_title: "Practice nurse", employer: "Hill Clinic", stage: "saved", applied_on: null })]);
    const { user, router } = renderApp("/applications?view=list&sort=role&dir=asc", { signedIn: true });
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((r) => within(r).getAllByRole("cell")[0]!.textContent)).toEqual(["Practice nurse", "Ward nurse"]);
    expect(within(table).getByRole("columnheader", { name: "Role" })).toHaveAttribute("aria-sort", "ascending");
    await user.selectOptions(screen.getByLabelText("Stage"), "saved");
    expect(router.state.location.search).toContain("stage=saved");
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(2);
  });
});

describe("an application", () => {
  it("previews what a reschedule does to preparation, and moves only the ticked times", async () => {
    asUser();
    const ev = { id: "e1", kind: "interview" as const, title: "Panel interview", on_date: "2026-12-16", local_time: "14:00", timezone: "Europe/London", starts_at: "2026-12-16T14:00:00Z", notes: "", created_at: now() };
    fakeApps([app({ stage: "interviewing", events: [ev] })]);
    const preview = {
      event_id: "e1", event_title: "Panel interview", event_starts_at: "2026-12-16T14:00:00Z", event_on_date: "2026-12-16", event_local_time: "14:00", event_timezone: "Europe/London",
      entries: [
        { id: "p1", title: "Prepare: Panel interview (Mercy General)", sequence: 2, follows_interview: true, status: "can_move" as const,
          current: { on_date: "2026-12-13", local_time: "18:00", timezone: "Europe/London", starts_at: "2026-12-13T18:00:00Z", all_day: false },
          proposal: { on_date: "2026-12-14", local_time: "22:00", timezone: "Europe/London", starts_at: "2026-12-14T22:00:00Z", all_day: false },
          note: "Keeps the same 40 hours before the interview." },
        { id: "p2", title: "Prepare: Panel interview (Mercy General)", sequence: 0, follows_interview: false, status: "fixed" as const,
          current: { on_date: "2026-12-14", local_time: "09:00", timezone: "Europe/London", starts_at: "2026-12-14T09:00:00Z", all_day: false },
          proposal: null, note: "A fixed time: it stays where it is." },
      ],
    };
    let sent: unknown = null;
    let fail = true;
    server.use(
      http.get(`${API}/api/v1/me/applications/a1/events/e1/prep`, () => HttpResponse.json(preview)),
      http.post(`${API}/api/v1/me/applications/a1/events/e1/prep/shift`, async ({ request }) => {
        sent = await request.json();
        if (fail) {
          fail = false;
          return HttpResponse.json({ error: { code: "interview_changed", message: "The interview's time changed again since this preview. Nothing was moved; review it again.", request_id: "r" } }, { status: 409 });
        }
        return HttpResponse.json({ moved: ["p1"], already_aligned: [], preview: { ...preview, entries: [{ ...preview.entries[0]!, status: "aligned", proposal: null, note: "Already matches the interview's current time." }, preview.entries[1]] } });
      }),
    );
    const { user } = renderApp("/applications/a1", { signedIn: true });
    await user.click(await screen.findByText("Preparation times"));
    const tick = await screen.findByRole("checkbox", { name: /Prepare: Panel interview .*→/ });
    expect(tick).not.toBeChecked(); // nothing is chosen for the learner
    expect(screen.getByText(/A fixed time: it stays where it is/)).toBeInTheDocument();
    const moveBtn = screen.getByRole("button", { name: "Move selected (0)" });
    expect(moveBtn).toBeDisabled();
    await user.click(tick);
    await user.click(screen.getByRole("button", { name: "Move selected (1)" }));
    // The interview moved again in another tab: nothing moved, and the preview is reloaded.
    expect(await screen.findByText(/changed again since this preview\. Nothing was moved/)).toBeInTheDocument();
    expect(sent).toEqual({ event_starts_at: "2026-12-16T14:00:00Z", entries: [{ id: "p1", sequence: 2 }] });
    await user.click(await screen.findByRole("checkbox", { name: /Prepare: Panel interview .*→/ }));
    await user.click(screen.getByRole("button", { name: "Move selected (1)" }));
    expect(await screen.findByText("Moved 1.")).toBeInTheDocument();
    expect(screen.getByText(/Already matches the interview's current time/)).toBeInTheDocument();
  });

  it("asks which one when a time happens twice, and never shifts it silently", async () => {
    asUser();
    fakeApps([app()]);
    const bodies: Record<string, unknown>[] = [];
    server.use(http.post(`${API}/api/v1/me/applications/a1/events`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      bodies.push(body);
      if (body.fold === null) {
        return HttpResponse.json({ error: { code: "ambiguous_time", message: "01:30 happens twice in America/Chicago on 2026-11-01 (the clocks go back). Say which one you mean.", request_id: "r", details: { first: "", second: "", first_offset: "-0500", second_offset: "-0600" } } }, { status: 400 });
      }
      return HttpResponse.json(app({ events: [{ id: "e1", kind: "interview", title: "Night interview", on_date: "2026-11-01", local_time: "01:30", timezone: "America/Chicago", starts_at: "2026-11-01T07:30:00Z", notes: "", created_at: now() }] }));
    }));
    const { user } = renderApp("/applications/a1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Add an event" }));
    const form = screen.getByRole("form", { name: "New event" });
    await user.type(within(form).getByLabelText("What"), "Night interview");
    fireEvent.change(within(form).getByLabelText(/^Date/), { target: { value: "2026-11-01" } });
    fireEvent.change(within(form).getByLabelText(/^Time \(optional\)/), { target: { value: "01:30" } });
    await user.selectOptions(within(form).getByLabelText("Time zone"), "America/Chicago");
    await user.click(within(form).getByRole("button", { name: "Add event" }));
    expect(await screen.findByText(/happens twice/)).toBeInTheDocument();
    expect(within(form).getByRole("button", { name: "Add event" })).toBeDisabled();
    await user.click(within(form).getByLabelText(/The second one \(UTC-06:00\)/));
    await user.click(within(form).getByRole("button", { name: "Add event" }));
    await waitFor(() => expect(bodies.at(-1)).toMatchObject({ fold: 1, local_time: "01:30", timezone: "America/Chicago" }));
    expect(await screen.findByText(/01:30 America\/Chicago/)).toBeInTheDocument();
  });

  it("drafts a message from the facts typed, and creating it changes nothing", async () => {
    asUser();
    const { sent } = fakeApps([app()]);
    const { user } = renderApp("/applications/a1", { signedIn: true });
    const composer = (await screen.findByRole("heading", { name: "Write a message" })).closest(".card") as HTMLElement;
    await user.type(within(composer).getByLabelText(/^To/), "Ms Lee");
    await user.type(within(composer).getByLabelText(/^When/), "on Tuesday");
    const draft = within(composer).getByLabelText(/^Draft/) as HTMLTextAreaElement;
    expect(draft.value).toContain("Dear Ms Lee,");
    expect(draft.value).toContain("Thank you for your time on Tuesday talking with me about the Ward nurse role at Mercy General.");
    expect(within(composer).getByText(/CodeCoach doesn't send messages/)).toBeInTheDocument();
    expect(sent).toHaveLength(0);
    expect(screen.getByText("Applied", { selector: ".badge" })).toBeInTheDocument();
  });
});

describe("application details: exact save state", () => {
  it("'Saved.' only while the form still says exactly what the server accepted", async () => {
    asUser();
    const a = app();
    fakeApps([a]);
    let release!: () => void;
    const answered = new Promise<void>((r) => { release = r; });
    server.use(http.patch(`${API}/api/v1/me/applications/:id`, async ({ request }) => {
      const body = (await request.json()) as Partial<Application>;
      await answered; // a slow save
      return HttpResponse.json({ ...a, ...body });
    }));
    const { user } = renderApp(`/applications/${a.id}`, { signedIn: true });
    const details = await screen.findByRole("form", { name: "Details" });
    const notes = within(details).getByLabelText(/Notes/);
    await user.type(notes, "First");
    await user.click(within(details).getByRole("button", { name: "Save details" }));
    await user.type(notes, " and more"); // typed while it was saving
    release();
    await waitFor(() => expect(within(details).getByRole("button", { name: "Save details" })).not.toHaveAttribute("aria-busy"));
    expect(within(details).queryByText("Saved.")).toBeNull(); // the newer text wasn't saved
    expect(notes).toHaveValue(`${a.notes}First and more`);
    await user.click(within(details).getByRole("button", { name: "Save details" }));
    expect(await within(details).findByText("Saved.")).toBeInTheDocument();
    await user.type(notes, "!");
    expect(within(details).queryByText("Saved.")).toBeNull(); // an edit after saving: no longer saved
  });
});
