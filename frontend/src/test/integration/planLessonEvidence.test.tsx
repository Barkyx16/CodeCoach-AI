/**
 * A passed lesson check as new evidence for the plan (Volume 17, prompt 3; docs/PLAN_UPDATES.md): the
 * preview names it as a lesson check passed, links to the lesson and says what its skill's evidence
 * would move; the version an update made lists the lesson checks it read, by version; a version from
 * before lists none.
 */
import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Plan, PlanNews } from "@/api/types";

import { makePlan } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const HANDOFFS = "Shift handoffs: “Describe a time…” scored 40/100 and the check passed on the lesson “SBAR handoffs”, so the next version would suggest “Retry: Describe a time…”.";
const NEWS: PlanNews = {
  text: "1 answer and 1 lesson check passed since this plan, below 70.", answers: 1, retries: 0, below: 1, rounds: 0, submissions: 0, not_passed: 0, lessons: 1,
  entries: [
    { kind: "answer", title: "Describe a time…", score: 40, exercise: false, skill: "shift handoffs", href: "/careers/registered-nurse/questions/e-good-7?answer=a-1" },
    { kind: "lesson", title: "SBAR handoffs", score: null, exercise: false, skill: "shift handoffs", href: "/learn/rn-sbar-handoff" },
  ],
  not_counted: ["1 lesson check passed on a version the lesson has since replaced isn’t counted: pass its current version."],
  by_skill: [{ skill: "shift handoffs", count: 2, text: HANDOFFS }],
};
const nurse = (version: number, extra: Partial<Plan> = {}): Plan => ({ ...makePlan(15), version, ...extra });

describe("A lesson check as new evidence for the plan", () => {
  it("names the check, links the lesson and lists what the update read", async () => {
    let plan = nurse(1, { news: NEWS, read_lessons: null });
    server.use(
      http.get(`${API}/api/v1/me/plan`, () => HttpResponse.json(plan)),
      http.post(`${API}/api/v1/me/plan/update`, () => {
        plan = nurse(2, {
          news: null,
          changes: ["Updated when you asked: 1 answer and 1 lesson check passed since version 1, below 70."],
          read_lessons: [
            { unit_id: "rn-sbar-handoff", version: 1, title: "SBAR handoffs", href: "/learn/rn-sbar-handoff" },
            { unit_id: "rn-gone", version: 2, title: null, href: null },
          ],
        });
        return HttpResponse.json(plan);
      }),
    );
    const { user } = renderApp("/plan", { signedIn: true });
    const news = await screen.findByRole("region", { name: /1 lesson check passed since this plan/ });
    expect(within(news).getByRole("list", { name: "What it would change, by skill" })).toHaveTextContent(HANDOFFS);
    await user.click(within(news).getByText("What's new (2)"));
    expect(within(news).getByRole("link", { name: "Lesson check passed: SBAR handoffs" })).toHaveAttribute("href", "/learn/rn-sbar-handoff");
    expect(news).toHaveTextContent("on a version the lesson has since replaced isn’t counted");
    await user.click(within(news).getByRole("button", { name: "Update my plan" }));
    const read = await screen.findByRole("list", { name: "Lesson checks this update read" });
    expect(within(read).getByRole("link", { name: "SBAR handoffs" })).toHaveAttribute("href", "/learn/rn-sbar-handoff");
    expect(read).toHaveTextContent("check passed on version 1");
    expect(read).toHaveTextContent("A lesson that's no longer offered · check passed on version 2");
  });

  it("a version from before lists no lesson checks", async () => {
    server.use(http.get(`${API}/api/v1/me/plan`, () => HttpResponse.json(nurse(3, { news: null, read_lessons: null, changes: ["Your plan moved on."] }))));
    renderApp("/plan", { signedIn: true });
    await screen.findByText("Your plan moved on.");
    expect(screen.queryByRole("list", { name: "Lesson checks this update read" })).not.toBeInTheDocument();
  });
});
