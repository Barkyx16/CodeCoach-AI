/**
 * Accepted improvements (Volume 12, prompt 1; docs/ACCEPTED_ACTIONS.md): accepting from the replay
 * sends which suggestion (never its words) once; the plan shows the action beside the plan with
 * where it came from, practice since, and done as the learner's word; a weekly action's weeks are
 * done one at a time; a stale edit shows both versions; the kit holds the action by id (ticking it is
 * the action, not a kit save; adding one saves only its id; templates leave it out); the schedule's
 * occurrence marks the same action done.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { AcceptedAction, Interview, InterviewReview, Kit, ScheduleEntry } from "@/api/types";
import { todayIn } from "@/features/applications/dates";

import { nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = new Date().toISOString();
const KEY = "point:Explains what you personally did";
const TITLE = "Explains what you personally did";

const interview = (): Interview => ({
  id: "iv-r", kind: "questions", status: "completed", phase: null, phase_index: 2, phase_guide: null, problem: null,
  track: "registered-nurse", career_title: "Registered Nurse", questions: [], round_summary: null,
  duration_seconds: 900, started_at: now, deadline_at: now, ended_at: now, seconds_remaining: 0,
  candidate_turns_remaining: 30, provider: "built-in (offline)", turns: [], final_code: null, evaluation: null,
});

const review = (actionId: string | null = null): InterviewReview => ({
  id: "iv-r", kind: "questions", track: "registered-nurse", career_title: "Registered Nurse", problem: null,
  status: "completed", status_label: "Completed", completed: true, started_at: now, ended_at: now,
  elapsed_seconds: 240, time_limit_seconds: 900, notices: [],
  items: [{
    key: "q1", index: 1, title: "A hard shift", prompt: "Tell me about a hard shift.", kind: "behavioral", role: "question",
    status: "answered", asked_at: now, answer_text: "We handled it as a team.", answered_at: now, source: "typed",
    transcription_note: null, engagement: null, feedback: { ...nurseAnswer, id: "a-1" }, dimensions: [], retries: 0,
    in_review_queue: false, question_id: "e-time-0",
  }],
  overall: [],
  improvements: [{
    key: KEY, title: TITLE, why: "Say “I” for your own actions. Missing in 1 of 1 answers.",
    evidence: [{ item_key: "q1", label: "A hard shift", excerpt: "We handled it as a team." }],
    practice: { label: "Retry “A hard shift”", retry_index: 1, href: null }, action_id: actionId,
  }],
  evaluation_available: true, evaluator: "built-in (offline)", disclaimer: "Scores come from the built-in rubric.", final_code: null,
});

const action = (over: Partial<AcceptedAction> = {}): AcceptedAction => ({
  id: "act-1", title: TITLE, notes: "", practice_href: "/interviews/iv-r/retry/1", practice_label: "Retry “A hard shift”",
  recurrence: "once", status: "open", done_at: null,
  source: {
    kind: "interview_improvement", interview_id: "iv-r", key: KEY, label: TITLE, why: "Say “I” for your own actions. Missing in 1 of 1 answers.",
    interview_title: "Registered Nurse interview", interview_date: "2026-11-03T09:00:00Z", versions: [{ question: "A hard shift", version: 2 }], available: true,
  },
  occurrences: [], attempts_since: 0, revision: 1, save_replay: null, created_at: now, updated_at: now, ...over,
});

const occurrence = (id: string, onDate: string, done = false) => ({
  id, on_date: onDate, all_day: true, local_time: null, timezone: null, starts_at: null, status: "scheduled" as const, sequence: 0,
  completed_at: done ? now : null,
});

let sent: { method: string; path: string; body: unknown }[] = [];
function record() {
  sent = [];
  server.events.removeAllListeners();
  server.events.on("request:start", async ({ request }) => {
    const path = new URL(request.url).pathname;
    if (request.method === "GET" || !/actions|kit|schedule/.test(path)) return;
    sent.push({ method: request.method, path, body: await request.clone().json().catch(() => null) });
  });
}
afterEach(() => { server.events.removeAllListeners(); });

describe("An improvement accepted from the replay", () => {
  it("sends which suggestion it was, once, and says where it went; the review stays as it was", async () => {
    let accepted: string | null = null;
    record();
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/interviews/iv-r`, () => HttpResponse.json(interview())),
      http.get(`${API}/api/v1/interviews/iv-r/review`, () => HttpResponse.json(review(accepted))),
      http.post(`${API}/api/v1/me/actions`, () => { accepted = "act-1"; return HttpResponse.json(action(), { status: 201 }); }),
    );
    const { user } = renderApp("/interviews/iv-r", { signedIn: true });
    const button = await screen.findByRole("button", { name: `Accept as an action: ${TITLE}` }, { timeout: 3000 });
    await user.click(button);
    expect(await screen.findByText(/Accepted as an action\./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See it on your plan" })).toHaveAttribute("href", "/plan#accepted-actions");
    await waitFor(() => expect(sent.filter((s) => s.path === "/api/v1/me/actions")).toHaveLength(1));
    // Which suggestion, never its words: the server reads them from its own review.
    expect(sent[0]!.body).toEqual({ source: { kind: "interview_improvement", interview_id: "iv-r", key: KEY }, recurrence: "once" });
    expect(screen.getByText("Say “I” for your own actions. Missing in 1 of 1 answers.")).toBeInTheDocument();
  });

  it("a review read again shows it accepted, with no second button", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/interviews/iv-r`, () => HttpResponse.json(interview())),
      http.get(`${API}/api/v1/interviews/iv-r/review`, () => HttpResponse.json(review("act-1"))),
    );
    renderApp("/interviews/iv-r", { signedIn: true });
    expect(await screen.findByText(/Accepted as an action\./, undefined, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /as an action/ })).toBeNull();
  });
});

describe("Improvements you accepted, beside the plan", () => {
  function servePlan(actions: AcceptedAction[], after?: AcceptedAction[]) {
    let current = actions;
    record();
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/me/actions`, () => HttpResponse.json(current)),
      http.post(`${API}/api/v1/me/actions/:id/:op`, () => { current = after ?? current; return HttpResponse.json(current[0]); }),
      http.post(`${API}/api/v1/me/actions/:id/occurrences/:entry/:op`, () => { current = after ?? current; return HttpResponse.json(current[0]); }),
    );
  }

  it("says where it came from, what was practised since, and done is the learner's word", async () => {
    const day = todayIn("UTC", new Date(Date.now() + 86_400_000));
    servePlan([action({ occurrences: [occurrence("o1", day)] })], [action({ status: "done", done_at: now, occurrences: [occurrence("o1", day, true)] })]);
    const { user } = renderApp("/plan", { signedIn: true });
    const section = await screen.findByRole("region", { name: "Improvements you accepted (1)" }, { timeout: 3000 });
    expect(section).toHaveTextContent(`From your Registered Nurse interview on`);
    expect(section).toHaveTextContent(`“${TITLE}”.`);
    expect(section).toHaveTextContent("Say “I” for your own actions. Missing in 1 of 1 answers.");
    expect(section).toHaveTextContent("A hard shift (question version 2)");
    expect(section).toHaveTextContent("Not practised since you accepted it.");
    expect(section).toHaveTextContent("Marking one done is your word: it changes no score.");
    expect(within(section).getByRole("link", { name: "Move it on your schedule" })).toHaveAttribute("href", "/schedule");
    expect(within(section).getByRole("link", { name: "Retry “A hard shift”" })).toHaveAttribute("href", "/interviews/iv-r/retry/1");
    expect(within(section).queryByRole("button", { name: "Schedule it" })).toBeNull(); // a one-off already on the schedule
    await user.click(within(section).getByRole("button", { name: `Mark done: ${TITLE}` }));
    await waitFor(() => expect(sent.map((s) => s.path)).toEqual(["/api/v1/me/actions/act-1/complete"]));
    expect(await screen.findByRole("region", { name: "Improvements you accepted (0)" })).toHaveTextContent("Done (1)");
  });

  it("a weekly action's weeks are done one at a time", async () => {
    const weekly = action({ recurrence: "weekly", occurrences: [occurrence("o1", "2026-11-16"), occurrence("o2", "2026-11-23"), occurrence("o3", "2026-11-30")] });
    servePlan([weekly]);
    const { user } = renderApp("/plan", { signedIn: true });
    const section = await screen.findByRole("region", { name: "Improvements you accepted (1)" }, { timeout: 3000 });
    expect(within(section).queryByRole("button", { name: /Mark done/ })).toBeNull(); // not the whole action at once
    const weeks = within(section).getAllByRole("checkbox");
    expect(weeks).toHaveLength(3);
    await user.click(weeks[0]!);
    await waitFor(() => expect(sent.map((s) => s.path)).toEqual(["/api/v1/me/actions/act-1/occurrences/o1/complete"]));
  });

  it("a stale edit shows both versions, and keeping mine saves over the version seen", async () => {
    servePlan([action()]);
    const patches: Record<string, unknown>[] = [];
    server.use(http.patch(`${API}/api/v1/me/actions/act-1`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      patches.push(body);
      if (body.expected_revision === 1) {
        return HttpResponse.json({ error: { code: "stale_revision", message: "Changed", request_id: "r", details: { current_revision: 2, current: action({ notes: "From the other tab", revision: 2 }) } } }, { status: 409 });
      }
      return HttpResponse.json(action({ notes: String(body.notes), revision: 3 }));
    }));
    const { user } = renderApp("/plan", { signedIn: true });
    const section = await screen.findByRole("region", { name: "Improvements you accepted (1)" }, { timeout: 3000 });
    await user.click(within(section).getByRole("button", { name: `Edit: ${TITLE}` }));
    await user.type(within(section).getByLabelText("Your notes"), "Say I, not we.");
    await user.click(within(section).getByRole("button", { name: "Save" }));
    expect(await within(section).findByText("From the other tab")).toBeInTheDocument();
    expect(within(section).getByLabelText("Your notes")).toHaveValue("Say I, not we."); // nothing lost
    await user.click(within(section).getByRole("button", { name: "Keep my version" }));
    await waitFor(() => expect(patches).toHaveLength(2));
    expect(patches[1]).toMatchObject({ notes: "Say I, not we.", expected_revision: 2 });
  });
});

describe("An accepted improvement on an interview kit's checklist", () => {
  const kit = (over: Partial<Kit> = {}): Kit => ({
    event_id: "e1", application_id: "a1", role_title: "Ward nurse", employer: "Mercy General", event_title: "Panel interview", event_kind: "interview",
    on_date: "2026-11-12", local_time: "10:00", timezone: "Europe/London", starts_at: "2026-11-12T10:00:00Z", format: "remote", location: "",
    meeting_link: null, interviewers: [], notes: "",
    checklist: [
      { id: "s-0", text: "Confirm the date, time and time zone", origin: "suggested", done: false, hidden: false },
      { id: "k-a", origin: "action", action_id: "act-1", text: TITLE, done: false, hidden: false,
        action: { id: "act-1", title: TITLE, recurrence: "once", done: false, occurrences_done: 0, occurrences_total: 0, href: "/interviews/iv-r/retry/1" } },
    ],
    questions: [], stories: [], target_title: null, saved: true, revision: 3, rescheduled_from: null, missing_stories: 0, save_replay: null, ...over,
  });

  it("ticking it is the action itself (no kit save); adding another saves only its id; templates leave it out", async () => {
    record();
    const puts: Record<string, unknown>[] = [];
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/me/applications/a1/events/e1/kit`, () => HttpResponse.json(kit())),
      http.get(`${API}/api/v1/me/schedule/settings`, () => HttpResponse.json({ timezone: null, reminders: false, reminder_minutes: 10, quiet_start: null, quiet_end: null })),
      http.get(`${API}/api/v1/me/kit-templates`, () => HttpResponse.json([])),
      http.get(`${API}/api/v1/me/actions`, () => HttpResponse.json([action(), action({ id: "act-2", title: "Answer the questions you didn't get to", source: { ...action().source, key: "unanswered" } })])),
      http.post(`${API}/api/v1/me/actions/act-1/complete`, () => HttpResponse.json(action({ status: "done", done_at: now }))),
      http.put(`${API}/api/v1/me/applications/a1/events/e1/kit`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        puts.push(body);
        return HttpResponse.json(kit({ revision: 4 }));
      }),
    );
    const { user } = renderApp("/applications/a1/events/e1/kit", { signedIn: true });
    const item = await screen.findByRole("checkbox", { name: TITLE }, { timeout: 3000 });
    expect(screen.getByText("Accepted improvement")).toBeInTheDocument();
    await user.click(item);
    await waitFor(() => expect(sent.map((s) => s.path)).toEqual(["/api/v1/me/actions/act-1/complete"]));
    expect(await screen.findByRole("checkbox", { name: TITLE })).toBeChecked();
    expect(puts).toHaveLength(0); // the kit wasn't saved for it
    // The template preview copies words only: the action isn't part of it.
    await user.click(screen.getByRole("button", { name: "Save as a template…" }));
    const keep = screen.getByRole("group", { name: "Checklist items to keep" });
    expect(within(keep).getByRole("checkbox", { name: "Confirm the date, time and time zone" })).toBeInTheDocument();
    expect(within(keep).queryByRole("checkbox", { name: TITLE })).toBeNull();
    // Add another accepted improvement: saved with the kit, as its id only.
    await user.selectOptions(screen.getByLabelText("Add an improvement you accepted"), "act-2");
    await user.click(screen.getByRole("button", { name: "Add to checklist" }));
    await user.click(screen.getByRole("button", { name: /Save kit|Save changes/ }));
    await waitFor(() => expect(puts).toHaveLength(1));
    const list = puts[0]!.checklist as { origin: string; action_id?: string }[];
    expect(list.filter((c) => c.origin === "action").map((c) => c.action_id)).toEqual(["act-1", "act-2"]);
  });
});

describe("An accepted improvement on the schedule", () => {
  it("is labelled, and marking it done there marks the same action", async () => {
    record();
    const day = todayIn(Intl.DateTimeFormat().resolvedOptions().timeZone, new Date());
    const entry: ScheduleEntry = {
      id: "o1", uid: "u1@codecoach", kind: "accepted_action", ref: "act-1", title: TITLE, href: "/interviews/iv-r/retry/1",
      all_day: true, on_date: day, local_time: null, timezone: null, starts_at: null, ends_at: null, duration_min: 30, status: "scheduled",
      done_at: null, available: true, conflicts: [], sequence: 0, notes: "", created_at: now, follows_interview: false,
    };
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/me/schedule/settings`, () => HttpResponse.json({ timezone: null, reminders: false, reminder_minutes: 10, quiet_start: null, quiet_end: null })),
      http.get(`${API}/api/v1/me/schedule/schedulable`, () => HttpResponse.json([])),
      http.get(`${API}/api/v1/me/schedule`, () => HttpResponse.json([entry])),
      http.post(`${API}/api/v1/me/actions/act-1/occurrences/o1/complete`, () => HttpResponse.json(action({ status: "done" }))),
    );
    const { user } = renderApp("/schedule", { signedIn: true });
    expect(await screen.findByText("Accepted improvement", undefined, { timeout: 3000 })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: `Mark done: ${TITLE}` }));
    await waitFor(() => expect(sent.map((s) => s.path)).toEqual(["/api/v1/me/actions/act-1/occurrences/o1/complete"]));
  });
});
