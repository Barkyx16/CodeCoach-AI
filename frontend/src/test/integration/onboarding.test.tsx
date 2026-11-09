import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { matchRoutes } from "react-router-dom";

import type { Onboarding, OnboardingUpdate } from "@/api/types";
import { routes } from "@/app/router";
import { HELP_TOPICS } from "@/features/onboarding/helpTopics";

import { tokenResponse, user as baseUser } from "../fixtures";
import { onboardingState } from "../onboarding";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const guest = { ...baseUser, id: "g-1", email: null, display_name: "Guest", is_guest: true };
const asUser = (u: typeof baseUser = nurse) => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: u }))));
const QUESTION = "/careers/registered-nurse/questions/m-pressure-0";
const nurseStarter = { kind: "question" as const, track: "registered-nurse", ref: "m-pressure-0", title: "Patient assessment under pressure", difficulty: "easy", href: QUESTION, minutes: 5 };

/** A stand-in for the server: applies each change the way the API does and records it. */
function fakeOnboarding(initial: Partial<Onboarding>) {
  let state = onboardingState(initial);
  const sent: OnboardingUpdate[] = [];
  server.use(
    http.get(`${API}/api/v1/me/onboarding`, () => HttpResponse.json(state)),
    http.patch(`${API}/api/v1/me/onboarding`, async ({ request }) => {
      const body = (await request.json()) as OnboardingUpdate;
      sent.push(body);
      if (body.start_choice) state = { ...state, start_choice: body.start_choice, welcome_due: false };
      if (body.tour === "start") state = { ...state, tour_status: "in_progress", tour_kind: body.tour_kind ?? state.format, tour_step: body.tour_step ?? 0, resume_due: false };
      if (body.tour === "step") state = { ...state, tour_status: "in_progress", tour_step: Math.min(body.tour_step ?? 0, 4) };
      if (body.tour === "pause") state = { ...state, tour_status: "paused", resume_due: true };
      if (body.tour === "complete") state = { ...state, tour_status: "completed", resume_due: false };
      if (body.dismiss === "resume_tour") state = { ...state, resume_due: false };
      if (body.dismiss === "welcome") state = { ...state, welcome_due: false };
      if (body.career_intro_seen) state = { ...state, career_intro: null };
      return HttpResponse.json(state);
    }),
  );
  return sent;
}

beforeEach(() => {
  // jsdom lays nothing out; the tour treats elements without boxes as hidden.
  vi.spyOn(Element.prototype, "getClientRects").mockReturnValue([{}] as unknown as DOMRectList);
});
afterEach(() => vi.restoreAllMocks());

describe("the welcome", () => {
  it("offers a nurse a real nursing question, and starts the tour on that question's page", async () => {
    asUser();
    const sent = fakeOnboarding({ welcome_due: true, start_choice: null, format: "written", starter: nurseStarter });
    const { user, router } = renderApp("/welcome", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Welcome, Ada" })).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(within(main).getByText(/Registered Nurse/)).toBeInTheDocument();
    expect(within(main).getByText("Patient assessment under pressure")).toBeInTheDocument();
    expect(within(main).getByText(/built-in rubric coach/)).toBeInTheDocument();
    expect(within(main).queryByText(/java/i)).toBeNull(); // a nurse isn't introduced through code

    await user.click(screen.getByRole("button", { name: "Start the tour" }));
    await waitFor(() => expect(router.state.location.pathname).toBe(QUESTION));
    expect(sent[0]).toEqual({ start_choice: "intro", tour: "start", tour_kind: "written" });

    // Step 1 explains the real question, and its heading has focus for screen readers.
    const heading = await screen.findByRole("heading", { name: "Read the question" });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.getByText("Introduction · step 1 of 5")).toBeInTheDocument();
    await waitFor(() => expect(document.querySelector('[data-tour="question"]')).toHaveAttribute("data-tour-active"));

    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByRole("heading", { name: "Your answer" })).toHaveFocus();
    await waitFor(() => expect(screen.getByLabelText("Your answer")).toHaveAttribute("data-tour-active"));
    expect(sent.at(-1)).toEqual({ tour: "step", tour_step: 1 });
    // The answer box is never covered or disabled by the tour.
    await user.type(screen.getByLabelText("Your answer"), "Still mine.");
    expect(screen.getByLabelText("Your answer")).toHaveValue("Still mine.");

    for (let i = 0; i < 3; i++) await user.click(screen.getByRole("button", { name: "Next" }));
    // The last step's element appears only after feedback: the tour says so instead of breaking.
    expect(await screen.findByRole("heading", { name: "What to do next" })).toBeInTheDocument();
    expect(screen.getByText(/This part appears after you get feedback/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Finish" }));
    await waitFor(() => expect(screen.queryByText(/Introduction · step/)).toBeNull());
    expect(sent.at(-1)).toEqual({ tour: "complete" });
    expect(document.querySelector("[data-tour-active]")).toBeNull();
    expect(screen.getByLabelText("Your answer")).toHaveValue("Still mine."); // the draft is untouched
  });

  it("explains honestly when code can't be judged, and the library is one click away", async () => {
    asUser(guest);
    const sent = fakeOnboarding({ welcome_due: true, start_choice: null });
    const { user, router } = renderApp("/welcome", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Welcome to CodeCoach" })).toBeInTheDocument();
    expect(screen.getByText("Two Sum")).toBeInTheDocument();
    expect(await screen.findByText(/Code can't be judged on this server right now/)).toBeInTheDocument();
    expect(screen.getByText(/guest accounts are deleted after 30 days without activity/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open the library" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/problems"));
    expect(sent).toEqual([{ start_choice: "library" }]);
  });

  it("doesn't pull the learner back if they leave while “Not now” is still saving", async () => {
    asUser();
    fakeOnboarding({ welcome_due: true, start_choice: null, format: "written", starter: nurseStarter });
    let release: () => void = () => undefined;
    let reached = false;
    server.use(http.patch(`${API}/api/v1/me/onboarding`, async () => {
      reached = true;
      await new Promise<void>((resolve) => { release = resolve; });
      return HttpResponse.json(onboardingState({ welcome_due: false, start_choice: "later" }));
    }));
    const { user, router, queryClient } = renderApp("/welcome", { signedIn: true });
    const button = await screen.findByRole("button", { name: "Not now, take me to my dashboard" });
    await user.click(button);
    await waitFor(() => expect(reached).toBe(true)); // the save is on its way
    // The save finishes at the worst moment: in the same task the welcome leaves the screen, before
    // React's passive effects run. This used to depend on timing (it failed in CI run 184).
    const left = new Promise<void>((resolve) => {
      const watch = new MutationObserver(() => {
        if (!button.isConnected) { watch.disconnect(); release(); resolve(); }
      });
      watch.observe(document.body, { childList: true, subtree: true });
    });
    await router.navigate("/targets"); // the learner moves on before the save finishes
    await left;
    await waitFor(() => expect(queryClient.getQueryData<Onboarding>(["me", "onboarding"])?.start_choice).toBe("later"));
    await new Promise((r) => setTimeout(r, 50)); // anything the finished save would do has happened
    expect(router.state.location.pathname).toBe("/targets");
  });

  it("can be put off, and still offers a way forward if it can't load", async () => {
    asUser();
    const sent = fakeOnboarding({ welcome_due: true, start_choice: null, format: "written", starter: nurseStarter });
    const { user, router, unmount } = renderApp("/welcome", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Not now, take me to my dashboard" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/dashboard"));
    expect(sent).toEqual([{ start_choice: "later" }]);
    unmount();

    server.use(http.get(`${API}/api/v1/me/onboarding`, () => HttpResponse.json({ error: { code: "internal_error", message: "x", request_id: "r" } }, { status: 500 })));
    renderApp("/welcome", { signedIn: true });
    expect(await screen.findByRole("link", { name: "Go to the practice library" })).toHaveAttribute("href", "/problems");
  });
});

describe("the tour", () => {
  it("resumes at the saved step after a refresh, and leaving it gives focus back to the page", async () => {
    asUser();
    const sent = fakeOnboarding({ tour_status: "in_progress", tour_kind: "written", tour_step: 2, format: "written", starter: nurseStarter });
    const { user } = renderApp(QUESTION, { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Your draft is kept" })).toBeInTheDocument();
    expect(screen.getByText("Introduction · step 3 of 5")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Back" }));
    expect(await screen.findByRole("heading", { name: "Your answer" })).toBeInTheDocument();
    await user.keyboard("{Escape}"); // focus is in the panel: Esc leaves the tour
    await waitFor(() => expect(screen.queryByText(/Introduction · step/)).toBeNull());
    expect(sent.at(-1)).toEqual({ tour: "pause" });
    await waitFor(() => expect(screen.getByRole("main")).toHaveFocus());
  });

  it("can always be left, even when saving fails", async () => {
    asUser();
    fakeOnboarding({ tour_status: "in_progress", tour_kind: "written", tour_step: 0, format: "written", starter: nurseStarter });
    server.use(http.patch(`${API}/api/v1/me/onboarding`, () => HttpResponse.json({ error: { code: "network_error", message: "x", request_id: "r" } }, { status: 503 })));
    const { user } = renderApp(QUESTION, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Next" }));
    expect(await screen.findByRole("heading", { name: "Your answer" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Leave the introduction" }));
    await waitFor(() => expect(screen.queryByText(/Introduction · step/)).toBeNull());
  });

  it("moves on with every Next, even when an earlier step's reply arrives after a later step was taken", async () => {
    // CI run 277: three quick Nexts, and an older reply put the tour back a step; the last Next
    // then landed on the step before, so Finish never came.
    asUser();
    fakeOnboarding({ tour_status: "in_progress", tour_kind: "written", tour_step: 0, format: "written", starter: nurseStarter });
    let state = onboardingState({ tour_status: "in_progress", tour_kind: "written", tour_step: 0, format: "written", starter: nurseStarter });
    const sent: OnboardingUpdate[] = [];
    let release!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    let firstReplied = false;
    server.use(http.patch(`${API}/api/v1/me/onboarding`, async ({ request }) => {
      const body = (await request.json()) as OnboardingUpdate;
      sent.push(body);
      if (body.tour === "step") state = { ...state, tour_step: Math.min(body.tour_step ?? 0, 4) };
      if (body.tour === "complete") state = { ...state, tour_status: "completed" };
      const reply = HttpResponse.json(state); // the state as this request left it
      if (sent.length === 1) {
        await held; // its reply comes back late
        firstReplied = true;
      }
      return reply;
    }));
    const { user } = renderApp(QUESTION, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Introduction · step 3 of 5")).toBeInTheDocument();
    await waitFor(() => expect(sent).toHaveLength(2));
    release(); // "step 2" arrives after "step 3" was answered
    await waitFor(() => expect(firstReplied).toBe(true));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.getByText("Introduction · step 3 of 5")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Introduction · step 5 of 5")).toBeInTheDocument();
    expect(sent.map((b) => b.tour_step)).toEqual([1, 2, 3, 4]);
    await user.click(screen.getByRole("button", { name: "Finish" }));
    await waitFor(() => expect(screen.queryByText(/Introduction · step/)).toBeNull());
  });

  it("doesn't run on a page of the other kind", async () => {
    asUser();
    fakeOnboarding({ tour_status: "in_progress", tour_kind: "coding", tour_step: 0 });
    renderApp(QUESTION, { signedIn: true });
    expect(await screen.findByLabelText("Your answer")).toBeInTheDocument();
    expect(screen.queryByText(/Introduction · step/)).toBeNull();
  });
});

describe("the dashboard", () => {
  it("offers to resume a tour that was left, once, and goes back to the same step", async () => {
    asUser();
    const sent = fakeOnboarding({ tour_status: "paused", tour_kind: "written", tour_step: 3, resume_due: true, format: "written", starter: nurseStarter });
    const { user, router } = renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByText("You left the introduction at step 4 of 5.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Resume" }));
    await waitFor(() => expect(router.state.location.pathname).toBe(QUESTION));
    expect(sent).toEqual([{ tour: "step", tour_step: 3 }]);
    expect(await screen.findByRole("heading", { name: "Getting feedback" })).toBeInTheDocument();
  });

  it("can dismiss the reminder, and after a career change offers that job's introduction", async () => {
    asUser();
    let sent = fakeOnboarding({ tour_status: "paused", tour_kind: "written", tour_step: 1, resume_due: true, format: "written", starter: nurseStarter });
    const { user, unmount } = renderApp("/dashboard", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Dismiss" }));
    await waitFor(() => expect(screen.queryByText(/You left the introduction/)).toBeNull());
    expect(sent).toEqual([{ dismiss: "resume_tour" }]);
    unmount();

    sent = fakeOnboarding({ format: "written", starter: nurseStarter, career_intro: { track: "registered-nurse", title: "Registered Nurse", kind: "written" } });
    const second = renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByText("You're now practising for Registered Nurse.")).toBeInTheDocument();
    expect(screen.getByText(/Your earlier practice is kept/)).toBeInTheDocument();
    await second.user.click(screen.getByRole("button", { name: "Not now" }));
    await waitFor(() => expect(screen.queryByText(/now practising for/)).toBeNull());
    expect(sent).toEqual([{ career_intro_seen: true }]);
  });
});

describe("help", () => {
  it("is searchable, links only to real pages, and promises no support it doesn't have", async () => {
    const { user } = renderApp("/help");
    expect(await screen.findByRole("heading", { level: 1, name: "How CodeCoach works" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Search help"), "voice");
    expect(screen.getByText(/answers match/)).toBeInTheDocument();
    expect(screen.getByText("Can I answer out loud?")).toBeInTheDocument();
    expect(screen.queryByText("Where are my past answers and submissions?")).toBeNull();
    await user.clear(screen.getByLabelText("Search help"));
    await user.type(screen.getByLabelText("Search help"), "zzzz");
    expect(screen.getByText(/Nothing matches/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear the search" }));
    expect(screen.getByText("Where are my past answers and submissions?")).toBeInTheDocument();
    expect(document.querySelector('a[href^="mailto:"]')).toBeNull();
    expect(within(screen.getByRole("main")).getByRole("link", { name: "Sign in" })).toBeInTheDocument(); // the tour needs an account

    for (const link of HELP_TOPICS.flatMap((t) => t.items.flatMap((i) => i.links ?? []))) {
      if (link.external) expect(link.to).toMatch(/^https:\/\/github\.com\//);
      else expect(matchRoutes(routes, link.to)?.at(-1)?.route.path, link.to).not.toBe("*");
    }
  });

  it("replays the introduction from the start on a real page", async () => {
    asUser();
    const sent = fakeOnboarding({ tour_status: "completed", tour_kind: "written", tour_step: 4, format: "written", starter: nurseStarter });
    const { user, router } = renderApp("/help", { signedIn: true });
    expect(await screen.findByText("You finished the introduction.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Replay from the start" }));
    await waitFor(() => expect(router.state.location.pathname).toBe(QUESTION));
    expect(sent).toEqual([{ tour: "start", tour_kind: "written" }]);
    expect(await screen.findByRole("heading", { name: "Read the question" })).toBeInTheDocument();
  });
});
