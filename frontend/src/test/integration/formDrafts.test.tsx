/**
 * Unfinished goals, target jobs, postings and application details are kept in this browser and
 * offered back (Volume 9, prompt 2; NAVIGATION.md "Unfinished forms"). Never called saved; offered,
 * never applied by itself; per account; bounded; a malformed or older copy is ignored; another
 * tab's newer copy is never overwritten; a confirmed save removes only the copy it accepted.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Application, Target } from "@/api/types";
import { localWorkKeys } from "@/auth/localWork";
import { formDraftKey } from "@/hooks/useFormDraft";

import { nurseGoals, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const ada = { ...baseUser, career_track: "registered-nurse" };
const bea = { ...ada, id: "user-bea", email: "bea@example.com" };
const asUser = (u = ada) => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: u }))));
const goalsKey = (id = ada.id) => formDraftKey(id, "goals", "registered-nurse");
const stored = (key: string) => JSON.parse(localStorage.getItem(key) ?? "null") as { form: Record<string, unknown>; base: unknown; at: string; tab: string; v: number } | null;
const now = new Date().toISOString();

afterEach(() => localStorage.clear());

function goalsServer(put: () => Promise<Response> | Response = () => HttpResponse.json({ ...nurseGoals, saved: true })) {
  server.use(
    http.get(`${API}/api/v1/me/goals`, () => HttpResponse.json(nurseGoals)),
    http.put(`${API}/api/v1/me/goals`, () => put()),
  );
}

it("goals typed and left unsaved are kept here, offered back after a reload, restored, then saved", async () => {
  asUser();
  goalsServer();
  const first = renderApp("/plan/goals", { signedIn: true });
  await first.user.type(await screen.findByLabelText(/Specialty or focus/), "Emergency");
  expect(await screen.findByText("Unsaved changes, kept on this device.")).toBeInTheDocument();
  await waitFor(() => expect(stored(goalsKey())?.form.specialty).toBe("Emergency"));
  expect(screen.queryByText(/saved to your account/i)).not.toBeInTheDocument();
  first.unmount(); // a reload

  const again = renderApp("/plan/goals", { signedIn: true });
  const offer = await screen.findByRole("region", { name: "Unsaved changes found" });
  expect(offer).toHaveTextContent(/You have unsaved changes to your goals from .*, kept on this device\. They aren't saved to your account\./);
  expect(screen.getByLabelText(/Specialty or focus/)).toHaveValue(""); // nothing applied by itself
  await new Promise((resolve) => setTimeout(resolve, 600)); // longer than the write delay
  expect(stored(goalsKey())?.form.specialty).toBe("Emergency"); // an undecided copy isn't written over
  await again.user.click(within(offer).getByRole("button", { name: "Restore them" }));
  expect(screen.getByLabelText(/Specialty or focus/)).toHaveValue("Emergency");
  await again.user.click(screen.getByRole("button", { name: "Save goals" }));
  await waitFor(() => expect(again.router.state.location.pathname).toBe("/dashboard"));
  expect(localStorage.getItem(goalsKey())).toBeNull(); // accepted: its copy goes
});

it("Discard removes only that copy; a malformed or older-format copy is ignored and doesn't break the page", async () => {
  asUser();
  goalsServer();
  localStorage.setItem(goalsKey(), JSON.stringify({ v: 1, form: { ...nurseGoals, specialty: "ICU" }, base: null, at: now, tab: "t" }));
  localStorage.setItem("codecoach.display.v1", "{}"); // unrelated
  const { user, unmount } = renderApp("/plan/goals", { signedIn: true });
  await user.click(within(await screen.findByRole("region", { name: "Unsaved changes found" })).getByRole("button", { name: "Discard them" }));
  expect(localStorage.getItem(goalsKey())).toBeNull();
  expect(localStorage.getItem("codecoach.display.v1")).toBe("{}");
  unmount();

  for (const bad of ["not json{", JSON.stringify({ v: 0, form: {}, at: now }), JSON.stringify({ v: 1, form: { specialty: 3 }, at: now, tab: "t" })]) {
    localStorage.setItem(goalsKey(), bad);
    const r = renderApp("/plan/goals", { signedIn: true });
    expect(await screen.findByLabelText(/Specialty or focus/)).toHaveValue("");
    expect(screen.queryByRole("region", { name: "Unsaved changes found" })).not.toBeInTheDocument();
    expect(localStorage.getItem(goalsKey())).toBeNull();
    r.unmount();
  }
});

it("a copy older than the lifetime isn't offered", async () => {
  asUser();
  goalsServer();
  const old = new Date(Date.now() - 15 * 86_400_000).toISOString();
  localStorage.setItem(goalsKey(), JSON.stringify({ v: 1, form: { ...nurseGoals, specialty: "ICU" }, base: null, at: old, tab: "t" }));
  renderApp("/plan/goals", { signedIn: true });
  await screen.findByLabelText(/Specialty or focus/);
  expect(screen.queryByRole("region", { name: "Unsaved changes found" })).not.toBeInTheDocument();
});

it("when this browser refuses the copy, the page says so and offers Copy your work", async () => {
  asUser();
  goalsServer();
  const { user } = renderApp("/plan/goals", { signedIn: true });
  const specialty = await screen.findByLabelText(/Specialty or focus/);
  const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
  try {
    await user.type(specialty, "Emergency");
    expect(await screen.findByText(/this browser can't keep a copy: save them, or copy your work/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Copy your work" }));
    expect(await screen.findByText(/Copied\./)).toBeInTheDocument();
    expect(await navigator.clipboard.readText()).toContain("Emergency");
  } finally {
    spy.mockRestore();
  }
});

it("another account signing in on this browser is never offered the first account's copy", async () => {
  asUser(bea);
  goalsServer();
  localStorage.setItem(goalsKey(ada.id), JSON.stringify({ v: 1, form: { ...nurseGoals, specialty: "Ada's ICU" }, base: null, at: now, tab: "t" }));
  renderApp("/plan/goals", { signedIn: true });
  expect(await screen.findByLabelText(/Specialty or focus/)).toHaveValue("");
  expect(screen.queryByRole("region", { name: "Unsaved changes found" })).not.toBeInTheDocument();
  expect(stored(goalsKey(ada.id))?.form.specialty).toBe("Ada's ICU"); // left for Ada
  expect(localWorkKeys(ada.id)).toContain(goalsKey(ada.id)); // and deleted when Ada signs out here
});

it("another tab's newer copy isn't overwritten: this page says its changes are on the page only", async () => {
  asUser();
  goalsServer();
  const { user } = renderApp("/plan/goals", { signedIn: true });
  const specialty = await screen.findByLabelText(/Specialty or focus/);
  const theirs = JSON.stringify({ v: 1, form: { ...nurseGoals, specialty: "From the other tab" }, base: null, at: new Date(Date.now() + 1000).toISOString(), tab: "other" });
  localStorage.setItem(goalsKey(), theirs);
  await user.type(specialty, "Mine");
  expect(await screen.findByText(/Another tab of this browser has a newer copy of this form, kept as it was/)).toBeInTheDocument();
  expect(localStorage.getItem(goalsKey())).toBe(theirs);
});

describe("a posting kept against an older save", () => {
  function target(over: Partial<Target> = {}): Target {
    const round = { track: "registered-nurse", question_ids: ["e-good-0"], duration_minutes: 10, purpose: "practice", difficulty: null };
    return {
      id: "t-1", title: "ED Nurse", employer: "Mercy General", track: "registered-nurse", career_title: "Registered Nurse",
      interview_date: null, archived: false, selected: true, requirements: 0, gaps: 0, created_at: now, updated_at: "2026-11-09T04:00:00Z",
      description: "Responsibilities:\n- Triage", notes: null, extractor: "rule-based (no AI)", requirement_list: [],
      next_activity: { kind: "question", title: "Q", href: "/careers/registered-nurse/questions/e-good-0", why: "Why.", answered: false, best_score: null },
      targeted_session: { title: "Short", scope: "1.", round }, mock_interview: { title: "Mock", scope: "1.", round },
      recent_attempts: [], experience: [], days_to_interview: null, ...over,
    } as Target;
  }

  it("says the posting was saved again since, and restoring opens the editor with the copy", async () => {
    asUser();
    server.use(
      http.get(`${API}/api/v1/targets`, () => HttpResponse.json([])),
      http.get(`${API}/api/v1/targets/t-1`, () => HttpResponse.json(target())),
    );
    const key = formDraftKey(ada.id, "posting", "t-1");
    const copy = { title: "ED Nurse", employer: "Mercy General", description: "Responsibilities:\n- Triage\n- Nights", interview_date: "", notes: "" };
    localStorage.setItem(key, JSON.stringify({ v: 1, form: copy, base: "2026-11-08T10:00:00Z", at: now, tab: "t" }));
    const { user } = renderApp("/targets/t-1", { signedIn: true });
    const offer = await screen.findByRole("region", { name: "Unsaved changes found" });
    expect(offer).toHaveTextContent(/The posting was saved again after this copy was made/);
    await user.click(within(offer).getByRole("button", { name: "Restore them" }));
    expect(screen.getByLabelText("Job description")).toHaveValue("Responsibilities:\n- Triage\n- Nights");
  });
});

it("an application's details saved while more was typed keep a copy of the newer text", async () => {
  asUser();
  const app: Application = {
    id: "a1", employer: "Mercy General", role_title: "Ward nurse", stage: "applied", applied_on: null, next_action: "Call the recruiter",
    next_action_due: null, target: null, archived: false, next_event: null, updated_at: now, link: null, notes: "",
    notes_revision: 1, stories: [], events: [], history: [], created_at: now,
  };
  let current = app;
  let release!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  server.use(
    http.get(`${API}/api/v1/me/applications/:id`, () => HttpResponse.json(current)),
    http.patch(`${API}/api/v1/me/applications/:id`, async ({ request }) => {
      const body = (await request.json()) as Partial<Application>;
      await held;
      current = { ...current, employer: body.employer ?? current.employer, updated_at: new Date().toISOString() };
      return HttpResponse.json(current);
    }),
  );
  const key = formDraftKey(ada.id, "application", "a1");
  const { user } = renderApp("/applications/a1", { signedIn: true });
  const employer = await screen.findByLabelText("Employer");
  await user.type(employer, " Hospital");
  await user.click(screen.getByRole("button", { name: "Save details" }));
  await user.type(employer, " North");
  await waitFor(() => expect(stored(key)?.form.employer).toBe("Mercy General Hospital North")); // kept before the reply
  release();
  await waitFor(() => expect(current.employer).toBe("Mercy General Hospital"));
  // The accepted save removes only a copy of what it saved: the newer text's copy is never gone,
  // not even until the next write (a tab closed in that moment would lose it).
  for (let i = 0; i < 6; i++) {
    expect(stored(key)?.form.employer).toBe("Mercy General Hospital North");
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  expect(screen.queryByText("Saved.")).not.toBeInTheDocument(); // not called saved while it differs
});

it("private notes typed while their save was on its way keep their browser copy (a Volume 8 prompt 5 fix)", async () => {
  asUser();
  const app: Application = {
    id: "a1", employer: "Mercy General", role_title: "Ward nurse", stage: "applied", applied_on: null, next_action: "Call",
    next_action_due: null, target: null, archived: false, next_event: null, updated_at: now, link: null, notes: "Recruiter: Sam",
    notes_revision: 1, stories: [], events: [], history: [], created_at: now,
  };
  let current = app;
  let release!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  server.use(
    http.get(`${API}/api/v1/me/applications/:id`, () => HttpResponse.json(current)),
    http.patch(`${API}/api/v1/me/applications/:id`, async ({ request }) => {
      const body = (await request.json()) as { notes?: string };
      await held;
      current = { ...current, notes: body.notes ?? current.notes, notes_revision: current.notes_revision + 1 };
      return HttpResponse.json(current);
    }),
  );
  const notesKey = `codecoach.appnotes.v1.${ada.id}.a1`;
  const { user } = renderApp("/applications/a1", { signedIn: true });
  const notes = await screen.findByLabelText(/Notes \(private\)/);
  await user.type(notes, ". Panel Tuesday");
  await user.click(screen.getByRole("button", { name: "Save details" }));
  await user.type(notes, ". Bring references");
  release();
  await waitFor(() => expect(current.notes).toBe("Recruiter: Sam. Panel Tuesday"));
  for (let i = 0; i < 4; i++) {
    expect(JSON.parse(localStorage.getItem(notesKey) ?? "null")?.notes).toBe("Recruiter: Sam. Panel Tuesday. Bring references");
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
});
