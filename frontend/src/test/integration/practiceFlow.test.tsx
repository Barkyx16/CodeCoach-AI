import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { InterviewSummary, PlanItem, ScheduleEntry } from "@/api/types";
import { rememberPlanOrigin } from "@/features/plan/planOrigin";

import { makePlan, page, planItems, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const QUESTION = "/careers/registered-nurse/questions/e-good-0";
const QUESTION_TITLE = "What good patient assessment looks like";

const extra = (id: string, position: number, title: string, minutes: number): PlanItem =>
  ({ ...planItems[1]!, id, position, title, minutes, href: `/careers/registered-nurse/questions/${id}` });
const withExtras = [...planItems, extra("item-q2", 3, "Explaining a care plan", 6), extra("item-q3", 4, "Handing over a patient", 8)];

describe("Today: using the time that's left", () => {
  it("offers one more pending activity that fits, adds it only when asked, then says honestly that nothing else fits", async () => {
    server.use(http.get(`${API}/api/v1/me/plan`, () => HttpResponse.json(makePlan(30, withExtras))));
    asNurse();
    const { user } = renderApp("/dashboard", { signedIn: true });
    const today = await screen.findByRole("region", { name: "Today's practice" });
    await user.click(within(today).getByRole("radio", { name: "30 min" }));
    // 12 + 6 planned of 30: the 20-minute mock doesn't fit the 12 left, the next 6-minute question does.
    expect(await within(today).findByText("About 12 of your 30 min left.")).toBeInTheDocument();
    expect(within(today).queryByRole("region", { name: "Added for today" })).not.toBeInTheDocument();
    await user.click(within(today).getByRole("button", { name: "Add another activity (Explaining a care plan, about 6 min)" }));

    const added = within(today).getByRole("region", { name: "Added for today" });
    expect(within(added).getByRole("article", { name: "Explaining a care plan" })).toBeInTheDocument();
    expect(within(today).getByText("Session estimate: about 24 min (with 1 added)")).toBeInTheDocument();
    expect(within(today).getByText("About 6 of your 30 min left.")).toBeInTheDocument();
    expect(within(today).getByText(/Nothing else in your plan fits that, and that's fine\./)).toBeInTheDocument();
    expect(within(today).queryByRole("button", { name: /Add another activity/ })).not.toBeInTheDocument();
  });

  it("points to due reviews when nothing in the plan fits", async () => {
    const due = { id: "rv-1", track: "registered-nurse", career_title: "Registered Nurse", question_id: "e-time-0", title: "A hard shift",
      href: "/careers/registered-nurse/questions/e-time-0", due_at: new Date().toISOString(), due: true, interval_days: 1, last_score: 41,
      reviews: 1, snoozed: false, why: "Due now." };
    server.use(
      http.get(`${API}/api/v1/me/plan`, () => HttpResponse.json(makePlan(30))),
      http.get(`${API}/api/v1/me/reviews`, () => HttpResponse.json({ due: [due], upcoming: [], ladder_days: [1, 3, 7, 14, 30], note: "" })),
    );
    asNurse();
    const { user } = renderApp("/dashboard", { signedIn: true });
    const today = await screen.findByRole("region", { name: "Today's practice" });
    await user.click(within(today).getByRole("radio", { name: "30 min" }));
    // 12 + 6 of 30 planned; the only other pending activity is the 20-minute mock.
    expect(await within(today).findByText("About 12 of your 30 min left.")).toBeInTheDocument();
    expect(within(today).getByRole("link", { name: "review 1 saved answer that is due" })).toHaveAttribute("href", "/reviews");
  });

  it("doesn't offer a top-up when less than 5 minutes are left", async () => {
    asNurse();
    renderApp("/dashboard", { signedIn: true });
    const today = await screen.findByRole("region", { name: "Today's practice" });
    // 15 minutes by default: the 12-minute baseline, and nothing else fits the 3 left.
    expect(await within(today).findByText("Session estimate: about 12 min")).toBeInTheDocument();
    expect(within(today).queryByText(/min left\./)).not.toBeInTheDocument();
    expect(within(today).queryByRole("button", { name: /Add another activity/ })).not.toBeInTheDocument();
  });
});

describe("Today: scheduling", () => {
  it("an activity already on the schedule shows when, and links to it instead of offering to schedule it again", async () => {
    const day = new Date(Date.now() + 3 * 86_400_000);
    const onDate = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
    const entry: ScheduleEntry = {
      id: "s-1", uid: "s-1@codecoach", kind: "plan_item", ref: "item-base", title: "Baseline check: 3 short questions", href: null,
      all_day: true, on_date: onDate, local_time: null, timezone: null, starts_at: null, ends_at: null, duration_min: 12,
      status: "scheduled", done_at: null, available: true, conflicts: [], sequence: 0, notes: "", created_at: new Date().toISOString(), follows_interview: false,
    };
    server.use(http.get(`${API}/api/v1/me/schedule`, () => HttpResponse.json([entry])));
    asNurse();
    const { user } = renderApp("/dashboard", { signedIn: true });
    const primary = await screen.findByRole("article", { name: "Baseline check: 3 short questions" });
    expect(await within(primary).findByText(/^Scheduled [^:]+$/)).toBeInTheDocument(); // the meta row; the menu link adds ": view or change"
    await user.click(within(primary).getByRole("button", { name: "More options" }));
    expect(within(primary).getByRole("link", { name: /^Scheduled .+: view or change$/ })).toHaveAttribute("href", "/schedule");
    expect(within(primary).queryByRole("link", { name: "Add to schedule" })).not.toBeInTheDocument();
  });

  it("an activity that isn't scheduled still offers to schedule it", async () => {
    asNurse();
    const { user } = renderApp("/dashboard", { signedIn: true });
    const primary = await screen.findByRole("article", { name: "Baseline check: 3 short questions" });
    await user.click(within(primary).getByRole("button", { name: "More options" }));
    expect(within(primary).getByRole("link", { name: "Add to schedule" })).toBeInTheDocument();
    expect(within(primary).queryByText(/^Scheduled /)).not.toBeInTheDocument();
  });
});

describe("Plan context on the activity page", () => {
  it("starting an activity from Today says it's from the plan on the page it opens", async () => {
    asNurse();
    const { user, router } = renderApp("/dashboard", { signedIn: true });
    const today = await screen.findByRole("region", { name: "Today's practice" });
    // At 5 minutes nothing fits, so the shortest activity (the 6-minute question) is offered.
    await user.click(within(today).getByRole("radio", { name: "5 min" }));
    const primary = await within(today).findByRole("article", { name: QUESTION_TITLE });
    await user.click(within(primary).getByRole("link", { name: "Start practice" }));
    await waitFor(() => expect(router.state.location.pathname).toBe(QUESTION));
    const note = await screen.findByRole("complementary", { name: "From your plan" });
    expect(note).toHaveTextContent(`From your plan: ${QUESTION_TITLE}. Done when: Submit an answer to this question.`);
    expect(within(note).getByRole("link", { name: /Back to your dashboard/ })).toHaveAttribute("href", "/dashboard");
  });

  it("once the server counts it as done, names the next step and leads back to it", async () => {
    const next = makePlan(15, planItems.filter((i) => i.id !== "item-q"));
    server.use(http.get(`${API}/api/v1/me/plan`, () => HttpResponse.json({
      ...next, version: 3, changes: [`Done: “${QUESTION_TITLE}” (answered, scored 80/100).`],
    })));
    asNurse();
    rememberPlanOrigin({ userId: nurse.id, itemId: "item-q", title: QUESTION_TITLE, target: QUESTION, from: "/plan" });
    renderApp(QUESTION, { signedIn: true });
    const note = await screen.findByRole("complementary", { name: "From your plan" });
    await waitFor(() => expect(note).toHaveTextContent(
      `Done for your plan: ${QUESTION_TITLE}. Next: Baseline check: 3 short questions (about 12 min).`));
    expect(within(note).getByRole("link", { name: /Continue your plan/ })).toHaveAttribute("href", "/plan");
  });

  it("can be hidden, and isn't shown to another account or on another page", async () => {
    asNurse();
    rememberPlanOrigin({ userId: nurse.id, itemId: "item-q", title: QUESTION_TITLE, target: QUESTION, from: "/dashboard" });
    const { user } = renderApp(QUESTION, { signedIn: true });
    const note = await screen.findByRole("complementary", { name: "From your plan" });
    await user.click(within(note).getByRole("button", { name: "Hide this note" }));
    expect(screen.queryByRole("complementary", { name: "From your plan" })).not.toBeInTheDocument();
  });

  it("an origin saved by another account is ignored", async () => {
    asNurse();
    rememberPlanOrigin({ userId: "someone-else", itemId: "item-q", title: QUESTION_TITLE, target: QUESTION, from: "/dashboard" });
    renderApp(QUESTION, { signedIn: true });
    expect(await screen.findByRole("heading", { name: QUESTION_TITLE, level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "From your plan" })).not.toBeInTheDocument();
  });

  it("isn't shown on a different page from the one the plan opened", async () => {
    asNurse();
    rememberPlanOrigin({ userId: nurse.id, itemId: "item-q", title: QUESTION_TITLE, target: QUESTION, from: "/dashboard" });
    renderApp("/dashboard", { signedIn: true });
    await screen.findByRole("region", { name: "Today's practice" });
    expect(screen.queryByRole("complementary", { name: "From your plan" })).not.toBeInTheDocument();
  });
});

describe("Ended-early mock interviews on the dashboard", () => {
  const round = (over: Partial<InterviewSummary>): InterviewSummary => ({
    id: "iv-1", kind: "questions", status: "abandoned", problem: null, track: "registered-nurse", career_title: "Registered Nurse",
    started_at: new Date(Date.now() - 3_600_000).toISOString(), ended_at: new Date(Date.now() - 3_000_000).toISOString(),
    overall: null, average_score: null, ...over,
  });
  let served = 0;
  const latestIs = (r: InterviewSummary) => {
    served = 0;
    server.use(http.get(`${API}/api/v1/interviews`, () => { served += 1; return HttpResponse.json(page([r])); }));
  };
  /** The list has been served and rendered, so an absent note is really absent. */
  const settled = async () => {
    await screen.findByRole("region", { name: "Today's practice" });
    await waitFor(() => expect(served).toBeGreaterThan(0));
    await new Promise((r) => setTimeout(r, 50));
  };

  it("points to the review of a round that ended early", async () => {
    latestIs(round({}));
    asNurse();
    renderApp("/dashboard", { signedIn: true });
    const note = await screen.findByRole("complementary", { name: "Your last mock interview ended early" });
    expect(within(note).getByRole("link", { name: /Review it/ })).toHaveAttribute("href", "/interviews/iv-1");
    expect(note).toHaveTextContent(/questions you didn't reach/);
  });

  it("says when a round ran out of time", async () => {
    latestIs(round({ status: "expired" }));
    asNurse();
    renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByRole("complementary", { name: "Your last mock interview ran out of time" })).toBeInTheDocument();
  });

  it("says nothing after a completed round, or a long-past one", async () => {
    latestIs(round({ status: "completed", overall: "Solid", average_score: 72 }));
    asNurse();
    const { unmount } = renderApp("/dashboard", { signedIn: true });
    await settled();
    expect(screen.queryByRole("complementary", { name: /Your last mock interview/ })).not.toBeInTheDocument();
    unmount();

    const old = new Date(Date.now() - 20 * 86_400_000).toISOString();
    latestIs(round({ started_at: old, ended_at: old }));
    renderApp("/dashboard", { signedIn: true });
    await settled();
    expect(screen.queryByRole("complementary", { name: /Your last mock interview/ })).not.toBeInTheDocument();
  });
});
