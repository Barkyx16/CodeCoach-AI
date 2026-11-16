import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Plan, PlanNews } from "@/api/types";

import { makePlan, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

/** New practice and "Update my plan" (Volume 13, prompt 1; docs/PLAN_UPDATES.md). */

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));

const NEWS: PlanNews = {
  text: "1 answer since this plan, below 70.",
  answers: 1, retries: 0, below: 1, rounds: 0, submissions: 0, not_passed: 0,
  entries: [{ kind: "answer", title: "Infection control on a busy ward", score: 52, exercise: false, href: "/careers/registered-nurse/questions/e-infection-1?answer=a1" }],
  not_counted: ["1 answer too short to score isn’t counted."],
};
const v = (version: number, news: PlanNews | null = null, changes?: string[]): Plan =>
  ({ ...makePlan(15), version, news, ...(changes ? { changes } : {}) });

/** The server's plan, changeable mid-test, and every update request's body. */
function serve(initial: Plan) {
  const state = { plan: initial, bodies: [] as unknown[] };
  server.use(http.get(`${API}/api/v1/me/plan`, () => HttpResponse.json(state.plan)));
  return state;
}

describe("New practice the plan doesn't use yet", () => {
  it("is one line with one button, and the plan stays until asked", async () => {
    asNurse();
    const state = serve(v(1, NEWS));
    server.use(http.post(`${API}/api/v1/me/plan/update`, async ({ request }) => {
      state.bodies.push(await request.json());
      state.plan = v(2, null, ["Updated when you asked: 1 answer since version 1, below 70.", "Added “Retry: Infection control on a busy ward”: Your best score is 52/100."]);
      return HttpResponse.json(state.plan);
    }));
    const { user } = renderApp("/plan", { signedIn: true });
    const news = await screen.findByRole("region", { name: /1 answer since this plan, below 70\./ });
    expect(news).toHaveTextContent("Your plan stays as it is until you update it.");
    expect(screen.getByText(/^Version 1\./)).toBeInTheDocument();
    await user.click(within(news).getByText("What's new (1)"));
    expect(within(news).getByRole("link", { name: "Answer: Infection control on a busy ward" })).toHaveAttribute("href", NEWS.entries[0]!.href);
    expect(news).toHaveTextContent("· 52/100");
    expect(news).toHaveTextContent("1 answer too short to score isn’t counted.");
    expect(state.bodies).toEqual([]); // reading never updates

    await user.click(within(news).getByRole("button", { name: "Update my plan" }));
    const done = await screen.findByText("Your plan is now version 2. What changed is listed with it.");
    expect(done).toHaveAttribute("role", "status");
    await waitFor(() => expect(done).toHaveFocus()); // the button is gone: focus goes to the result
    expect(state.bodies).toEqual([{ version: 1, track: "registered-nurse" }]);
    expect(await screen.findByText(/^Version 2\./)).toBeInTheDocument();
    expect(screen.getByText("Updated when you asked: 1 answer since version 1, below 70.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Update my plan" })).not.toBeInTheDocument();
  });

  it("another tab updated first: it says so and shows that version", async () => {
    asNurse();
    const state = serve(v(1, NEWS));
    server.use(http.post(`${API}/api/v1/me/plan/update`, () => {
      state.plan = v(2); // the other tab's version
      return HttpResponse.json(
        { error: { code: "plan_changed", message: "Your plan was already updated, in another tab or on another device: it's now version 2.", details: { version: 2 } } },
        { status: 409 },
      );
    }));
    const { user } = renderApp("/plan", { signedIn: true });
    const news = await screen.findByRole("region", { name: /1 answer since this plan/ });
    await user.click(within(news).getByRole("button", { name: "Update my plan" }));
    expect(await screen.findByText("Your plan was already updated, in another tab or on another device: this is version 2.")).toBeInTheDocument();
    expect(await screen.findByText(/^Version 2\./)).toBeInTheDocument();
    expect(screen.queryByText(/Your plan wasn't changed/)).not.toBeInTheDocument(); // told, not failed
  });

  it("nothing left to update: says so, and the version stays", async () => {
    asNurse();
    const state = serve(v(1, NEWS));
    server.use(http.post(`${API}/api/v1/me/plan/update`, () => {
      state.plan = v(1); // a dispute since, in another tab: what's new no longer changes it
      return HttpResponse.json(state.plan);
    }));
    const { user } = renderApp("/plan", { signedIn: true });
    const news = await screen.findByRole("region", { name: /1 answer since this plan/ });
    await user.click(within(news).getByRole("button", { name: "Update my plan" }));
    const said = await screen.findByText("Nothing to update: what's new no longer changes your plan.");
    await waitFor(() => expect(said).toHaveFocus());
    expect(screen.getByText(/^Version 1\./)).toBeInTheDocument();
  });

  it("a failed update says the plan wasn't changed and keeps the button", async () => {
    asNurse();
    serve(v(1, NEWS));
    server.use(http.post(`${API}/api/v1/me/plan/update`, () => HttpResponse.json({ error: { code: "internal", message: "Something went wrong." } }, { status: 500 })));
    const { user } = renderApp("/plan", { signedIn: true });
    const news = await screen.findByRole("region", { name: /1 answer since this plan/ });
    await user.click(within(news).getByRole("button", { name: "Update my plan" }));
    expect(await within(news).findByRole("alert")).toHaveTextContent("Your plan wasn't changed.");
    await waitFor(() => expect(within(news).getByRole("button", { name: "Update my plan" })).toBeEnabled());
  });

  it("the Today card says it too, in one line, and nothing shows without news", async () => {
    asNurse();
    const state = serve(v(1, NEWS));
    const first = renderApp("/dashboard", { signedIn: true });
    const today = await screen.findByRole("region", { name: "Today's practice" });
    const news = await within(today).findByRole("region", { name: /1 answer since this plan, below 70\./ });
    expect(within(news).getByRole("button", { name: "Update my plan" })).toBeInTheDocument();
    expect(within(news).queryByText(/What's new/)).not.toBeInTheDocument(); // compact
    first.unmount();

    state.plan = v(1);
    renderApp("/dashboard", { signedIn: true });
    const again = await screen.findByRole("region", { name: "Today's practice" });
    await within(again).findByText(/Session estimate/);
    expect(within(again).queryByRole("button", { name: "Update my plan" })).not.toBeInTheDocument();
  });
});

describe("A judged submission as new evidence (Volume 14, prompt 2)", () => {
  it("is named with its verdict, as judged", async () => {
    const news: PlanNews = {
      text: "1 submission (not passed) since this plan.", answers: 0, retries: 0, below: 0, rounds: 0, submissions: 1, not_passed: 1,
      entries: [{ kind: "submission", title: "Two Sum", score: null, verdict: "not passed", exercise: false, href: "/history/submissions/s-1" }], not_counted: [],
    };
    serve(v(1, news));
    const { user } = renderApp("/plan", { signedIn: true });
    const region = await screen.findByRole("region", { name: /1 submission \(not passed\) since this plan\./ });
    await user.click(within(region).getByText("What's new (1)"));
    expect(within(region).getByRole("link", { name: "Submission: Two Sum" })).toHaveAttribute("href", "/history/submissions/s-1");
    expect(region).toHaveTextContent("· not passed");
    expect(region.textContent).not.toMatch(/improv|better/i);
  });
});
