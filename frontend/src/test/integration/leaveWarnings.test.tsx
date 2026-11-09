/**
 * The remaining typed forms ask before leaving would discard them (Volume 9, prompt 1;
 * NAVIGATION.md): goals, a new target job, the job posting editor, and an application's details.
 * Dirty means "differs from what was loaded or last accepted": typing and putting it back isn't a
 * change. A successful save lets its own move through once; a failed save never does; text typed
 * while saving stays, and still counts as unsaved.
 */
import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Application, Target } from "@/api/types";

import { nurseGoals, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = new Date().toISOString();
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const home = () => screen.getByRole("link", { name: "CodeCoach AI home" });

let confirm: ReturnType<typeof vi.spyOn>;
beforeEach(() => { confirm = vi.spyOn(window, "confirm").mockReturnValue(false); });
afterEach(() => confirm.mockRestore());

describe("goals", () => {
  function goalsServer(put: () => Promise<Response> | Response = () => HttpResponse.json({ ...nurseGoals, saved: true })) {
    server.use(
      http.get(`${API}/api/v1/me/goals`, () => HttpResponse.json(nurseGoals)),
      http.put(`${API}/api/v1/me/goals`, () => put()),
    );
  }

  it("asks before discarding a change; staying keeps it; putting it back asks nothing", async () => {
    asNurse();
    goalsServer();
    const { user, router } = renderApp("/plan/goals", { signedIn: true });
    const specialty = await screen.findByLabelText(/Specialty or focus/);
    await user.type(specialty, "Emergency");
    await user.click(home());
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/^Your changes to your goals aren't saved, and leaving would discard them/));
    expect(router.state.location.pathname).toBe("/plan/goals");
    expect(screen.getByLabelText(/Specialty or focus/)).toHaveValue("Emergency"); // stayed, intact
    await user.clear(specialty); // back to what was loaded
    confirm.mockClear();
    await user.click(home());
    await waitFor(() => expect(router.state.location.pathname).not.toBe("/plan/goals"));
    expect(confirm).not.toHaveBeenCalled();
  });

  it("browser Back asks too, and staying keeps the change", async () => {
    asNurse();
    goalsServer();
    const { user, router } = renderApp("/dashboard", { signedIn: true });
    await act(() => router.navigate("/plan/goals"));
    await user.type(await screen.findByLabelText(/Specialty or focus/), "Emergency");
    await act(() => router.navigate(-1));
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(router.state.location.pathname).toBe("/plan/goals");
    expect(screen.getByLabelText(/Specialty or focus/)).toHaveValue("Emergency");
  });

  it("a successful save goes back without asking; a failed one still asks", async () => {
    asNurse();
    let fail = true;
    goalsServer(() => (fail
      ? HttpResponse.json({ error: { code: "internal_error", message: "boom", request_id: "r", details: null } }, { status: 500 })
      : HttpResponse.json({ ...nurseGoals, specialty: "Emergency", saved: true })));
    const { user, router } = renderApp("/plan/goals", { signedIn: true });
    await user.type(await screen.findByLabelText(/Specialty or focus/), "Emergency");
    await user.click(screen.getByRole("button", { name: "Save goals" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument(); // failed: no exemption
    await user.click(home());
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(router.state.location.pathname).toBe("/plan/goals");
    fail = false;
    confirm.mockClear();
    await user.click(screen.getByRole("button", { name: "Save goals" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/dashboard"));
    expect(confirm).not.toHaveBeenCalled();
  });

  it("typing while the save is on its way stays, still unsaved, and leaving asks", async () => {
    asNurse();
    let release!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    goalsServer(async () => { await held; return HttpResponse.json({ ...nurseGoals, specialty: "Emergency", saved: true }); });
    const { user, router } = renderApp("/plan/goals", { signedIn: true });
    const specialty = await screen.findByLabelText(/Specialty or focus/);
    await user.type(specialty, "Emergency");
    await user.click(screen.getByRole("button", { name: "Save goals" }));
    await user.type(specialty, " department");
    release();
    expect(await screen.findByText(/You changed more since: save again to keep those changes/)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/plan/goals");
    expect(specialty).toHaveValue("Emergency department");
    await user.click(home());
    expect(confirm).toHaveBeenCalledTimes(1);
  });
});

function target(): Target {
  const round = { track: "registered-nurse", question_ids: ["e-good-0"], duration_minutes: 10, purpose: "practice", difficulty: null };
  return {
    id: "t-1", title: "ED Nurse", employer: "Mercy General", track: "registered-nurse", career_title: "Registered Nurse",
    interview_date: null, archived: false, selected: true, requirements: 0, gaps: 0, created_at: now, updated_at: now,
    description: "Responsibilities:\n- Perform patient assessment", notes: null, extractor: "rule-based (no AI)",
    requirement_list: [],
    next_activity: { kind: "question", title: "What good patient assessment looks like", href: "/careers/registered-nurse/questions/e-good-0", why: "Practises patient assessment.", answered: false, best_score: null },
    targeted_session: { title: "Short targeted session", scope: "1 question.", round },
    mock_interview: { title: "Mock interview for ED Nurse", scope: "1 question.", round: { ...round, duration_minutes: 15 } },
    recent_attempts: [], experience: [], days_to_interview: null,
  } as Target;
}

describe("target jobs", () => {
  function targetServer() {
    let t = target();
    server.use(
      http.get(`${API}/api/v1/targets`, () => HttpResponse.json([])),
      http.post(`${API}/api/v1/targets`, () => HttpResponse.json(t, { status: 201 })),
      http.get(`${API}/api/v1/targets/t-1`, () => HttpResponse.json(t)),
      http.patch(`${API}/api/v1/targets/t-1`, async ({ request }) => {
        t = { ...t, ...((await request.json()) as Partial<Target>) };
        return HttpResponse.json(t);
      }),
    );
  }

  it("a new target job's typed description asks before leaving; creating it opens it without asking", async () => {
    asNurse();
    targetServer();
    const { user, router } = renderApp("/targets", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Add a target role" }));
    await user.type(screen.getByLabelText("Job description"), "Triage incoming patients");
    await user.click(home());
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/Your changes to the new target job aren't saved/));
    expect(screen.getByLabelText("Job description")).toHaveValue("Triage incoming patients");
    confirm.mockClear();
    await user.type(screen.getByLabelText(/Role title/), "ED Nurse");
    await user.click(screen.getByRole("button", { name: "Find requirements" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/targets/t-1"));
    expect(confirm).not.toHaveBeenCalled();
  });

  it("editing the posting asks before leaving; Cancel discards on purpose; a second edit after saving asks again", async () => {
    asNurse();
    targetServer();
    const { user, router } = renderApp("/targets/t-1", { signedIn: true });
    const posting = await screen.findByRole("heading", { name: "The posting" });
    const card = posting.closest(".card") as HTMLElement;
    await user.click(within(card).getByRole("button", { name: "Edit" }));
    const jd = within(card).getByLabelText("Job description");
    await user.type(jd, "\n- Night shifts");
    await user.click(home());
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/Your changes to the job posting aren't saved/));
    expect(jd).toHaveValue("Responsibilities:\n- Perform patient assessment\n- Night shifts");
    await user.click(within(card).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(within(card).queryByLabelText("Job description")).not.toBeInTheDocument());
    await user.click(within(card).getByRole("button", { name: "Edit" }));
    await user.type(within(card).getByLabelText("Role title"), " (nights)");
    confirm.mockClear();
    await user.click(home());
    expect(confirm).toHaveBeenCalledTimes(1);
    await user.click(within(card).getByRole("button", { name: "Cancel" }));
    confirm.mockClear();
    await user.click(home());
    await waitFor(() => expect(router.state.location.pathname).not.toBe("/targets/t-1"));
    expect(confirm).not.toHaveBeenCalled();
  });
});

describe("the posting, saved while typing", () => {
  it("text typed while the save is on its way keeps the editor open, and leaving asks", async () => {
    asNurse();
    let t = target();
    let release!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    server.use(
      http.get(`${API}/api/v1/targets`, () => HttpResponse.json([])),
      http.get(`${API}/api/v1/targets/t-1`, () => HttpResponse.json(t)),
      http.patch(`${API}/api/v1/targets/t-1`, async ({ request }) => {
        const body = (await request.json()) as Partial<Target>;
        await held;
        t = { ...t, ...body };
        return HttpResponse.json(t);
      }),
    );
    const { user } = renderApp("/targets/t-1", { signedIn: true });
    const card = (await screen.findByRole("heading", { name: "The posting" })).closest(".card") as HTMLElement;
    await user.click(within(card).getByRole("button", { name: "Edit" }));
    const title = within(card).getByLabelText("Role title");
    await user.type(title, " (days)");
    await user.click(within(card).getByRole("button", { name: "Save" }));
    await user.type(title, " and weekends");
    release();
    await waitFor(() => expect(t.title).toBe("ED Nurse (days)")); // what was sent is saved
    expect(within(card).getByLabelText("Role title")).toHaveValue("ED Nurse (days) and weekends"); // still open
    await user.click(home());
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/the job posting/));
  });
});

describe("application details", () => {
  function app(): Application {
    return {
      id: "a1", employer: "Mercy General", role_title: "Ward nurse", stage: "applied", applied_on: null, next_action: "Call the recruiter",
      next_action_due: null, target: null, archived: false, next_event: null, updated_at: now, link: null, notes: "",
      notes_revision: 1, stories: [], events: [], history: [], created_at: now,
    };
  }

  it("a changed detail other than the notes asks before leaving; once saved, leaving doesn't", async () => {
    asNurse();
    let current = app();
    server.use(
      http.get(`${API}/api/v1/me/applications/:id`, () => HttpResponse.json(current)),
      http.patch(`${API}/api/v1/me/applications/:id`, async ({ request }) => {
        const body = (await request.json()) as Partial<Application>;
        current = { ...current, employer: body.employer ?? current.employer };
        return HttpResponse.json(current);
      }),
    );
    const { user, router } = renderApp("/applications/a1", { signedIn: true });
    const employer = await screen.findByLabelText("Employer");
    await user.type(employer, " Hospital");
    await user.click(home());
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/Your changes to this application's details aren't saved/));
    expect(employer).toHaveValue("Mercy General Hospital");
    await user.click(screen.getByRole("button", { name: "Save details" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    confirm.mockClear();
    await user.click(home());
    await waitFor(() => expect(router.state.location.pathname).not.toBe("/applications/a1"));
    expect(confirm).not.toHaveBeenCalled();
  });
});
