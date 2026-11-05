import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { makePlan, nurseGoals, planItems, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));

describe("Today", () => {
  it("shows one next action with why, skill, time and what counts as done", async () => {
    asNurse();
    renderApp("/dashboard", { signedIn: true });
    const today = await screen.findByRole("region", { name: "Today's practice" });
    // 15 minutes by default: the 12-minute baseline is first and fits.
    const primary = await within(today).findByRole("article", { name: "Baseline check: 3 short questions" });
    expect(within(primary).getByText(/There isn't enough evidence to tailor your plan yet/)).toBeInTheDocument();
    expect(primary).toHaveTextContent("Baseline"); // its type; the skill, also "Baseline", isn't repeated
    expect(within(primary).getByText(/About 12 min/)).toBeInTheDocument();
    expect(within(primary).getByText(/Finish the baseline round/)).toBeInTheDocument();
    const week = within(today).getByRole("region", { name: "This week" });
    expect(week).toHaveTextContent("6 / 60 min planned"); // planned minutes keep their own label, apart from the session estimate
  });

  it("the time options really change the suggested session", async () => {
    const asked: number[] = [];
    server.use(http.get(`${API}/api/v1/me/plan`, ({ request }) => {
      const minutes = Number(new URL(request.url).searchParams.get("minutes"));
      asked.push(minutes);
      return HttpResponse.json(makePlan(minutes));
    }));
    asNurse();
    const { user } = renderApp("/dashboard", { signedIn: true });
    const today = await screen.findByRole("region", { name: "Today's practice" });
    await user.click(within(today).getByRole("radio", { name: "5 min" }));
    await waitFor(() => expect(asked).toContain(5));
    expect(await within(today).findByText(/Nothing fits|so here's one that fits 5/)).toBeInTheDocument();
    await user.click(within(today).getByRole("radio", { name: "30 min" }));
    expect(await within(today).findByRole("article", { name: "Baseline check: 3 short questions" })).toBeInTheDocument();
    expect(within(today).getByText(/^Next: /)).toBeInTheDocument(); // the follow-up, after the recommendation
    expect(within(today).getByText(/Session estimate: about 18 min/)).toBeInTheDocument();
  });

  it("setup can be skipped for a starter plan, and plan changes are explained", async () => {
    let body: unknown = null;
    server.use(http.put(`${API}/api/v1/me/goals`, async ({ request }) => {
      body = await request.json();
      return HttpResponse.json({ ...nurseGoals, saved: true, setup_skipped: true });
    }));
    asNurse();
    const { user } = renderApp("/dashboard", { signedIn: true });
    const today = await screen.findByRole("region", { name: "Today's practice" });
    expect(await within(today).findByText("Your plan changed")).toBeInTheDocument();
    expect(within(today).getByText(/Added “Retry: Patient assessment under pressure”/)).toBeInTheDocument();
    await user.click(within(today).getByRole("button", { name: "Got it" }));
    expect(within(today).queryByText("Your plan changed")).not.toBeInTheDocument();
    await user.click(within(today).getByRole("button", { name: "Not now, use a starter plan" }));
    await waitFor(() => expect(body).toMatchObject({ setup_skipped: true }));
  });

  it("skipping sends a skip (never a completion), and a round activity starts a real round", async () => {
    const actions: string[] = [];
    let start: unknown = null;
    server.use(
      http.post(`${API}/api/v1/me/plan/items/:id/:action`, ({ params }) => {
        actions.push(`${String(params.id)}:${String(params.action)}`);
        return HttpResponse.json({ ...planItems[1], status: "skipped" });
      }),
      http.post(`${API}/api/v1/interviews`, async ({ request }) => {
        start = await request.json();
        return HttpResponse.json({ id: "round-base" }, { status: 201 });
      }),
      http.get(`${API}/api/v1/me/plan`, () => HttpResponse.json(makePlan(30))),
    );
    asNurse();
    const { user, router } = renderApp("/dashboard", { signedIn: true });
    const primary = await screen.findByRole("article", { name: "Baseline check: 3 short questions" });
    expect(within(primary).queryByRole("button", { name: "Choose another" })).not.toBeInTheDocument();
    const follow = screen.getByRole("article", { name: "What good patient assessment looks like" });
    expect(follow).toHaveTextContent(`Skill: ${planItems[1]!.skill}`); // a skill unlike its type is shown
    await user.click(within(follow).getByRole("button", { name: "More options" }));
    expect(within(follow).getByRole("link", { name: "Add to schedule" })).toBeInTheDocument(); // scheduling and skipping stay distinct
    await user.click(within(follow).getByRole("button", { name: "Skip for now" }));
    await waitFor(() => expect(actions).toEqual(["item-q:skip"]));
    await user.click(within(primary).getByRole("button", { name: /Start/ }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/interviews/round-base"));
    expect(start).toMatchObject({ kind: "questions", purpose: "baseline", track: "registered-nurse", duration_minutes: 15 });
  });
});

describe("Today's controls", () => {
  it("time available is one labelled choice, and More options opens, closes on Escape and returns focus", async () => {
    asNurse();
    const { user } = renderApp("/dashboard", { signedIn: true });
    const today = await screen.findByRole("region", { name: "Today's practice" });
    const time = within(today).getByRole("group", { name: "Time available" });
    expect(within(time).getAllByRole("radio").map((r) => r.getAttribute("value"))).toEqual(["5", "15", "30"]);
    expect(within(time).getByRole("radio", { name: "15 min" })).toBeChecked();

    const primary = await within(today).findByRole("article", { name: "Baseline check: 3 short questions" });
    const actions = [...within(primary).queryAllByRole("link"), ...within(primary).queryAllByRole("button")];
    expect(actions.filter((el) => el.classList.contains("btn--primary")).map((el) => el.textContent?.trim())).toEqual(["Start practice"]); // one filled action
    const more = within(primary).getByRole("button", { name: "More options" });
    expect(more).toHaveAttribute("aria-expanded", "false");
    await user.click(more);
    expect(more).toHaveAttribute("aria-expanded", "true");
    await user.tab();
    expect(within(primary).getByRole("link", { name: "Add to schedule" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(more).toHaveAttribute("aria-expanded", "false");
    expect(more).toHaveFocus();
  });
});

describe("Plan page and goals", () => {
  it("keeps self-ratings, rubric scores and code results apart, with no single readiness score", async () => {
    asNurse();
    renderApp("/plan", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Your plan" })).toBeInTheDocument();
    expect(screen.getByText(/Building your baseline/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "What you told us" })).toBeInTheDocument();
    expect(screen.getByText("triage: 4 of 5 (your confidence)")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "How your answers scored" })).toBeInTheDocument();
    expect(screen.getByText("45/100")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Code the judge ran" })).not.toBeInTheDocument(); // nurses have no coding
    expect(screen.queryByText(/readiness/i)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Up next (3)" })).toBeInTheDocument();
  });

  it("saves optional goals without touching progress, and shows server validation", async () => {
    let body: Record<string, unknown> | null = null;
    server.use(http.put(`${API}/api/v1/me/goals`, async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ ...nurseGoals, ...body, saved: true });
    }));
    asNurse();
    const { user, router } = renderApp("/plan/goals", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Your goals" })).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /Experienced \(3-7 years\)/ }));
    await user.click(screen.getByRole("checkbox", { name: "Triage" }));
    await user.click(screen.getByRole("checkbox", { name: "Speaking out loud" }));
    expect(screen.queryByRole("checkbox", { name: "Coding problems" })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("triage"), "2");
    await user.click(screen.getByRole("button", { name: "Save goals" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/dashboard"));
    expect(body).toMatchObject({ experience: "mid", focus_areas: ["triage"], formats: ["written", "voice"], confidence: { triage: 2 } });
  });
});
