import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Plan, PlanNews } from "@/api/types";

import { makePlan } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

/** Judged code as new evidence for the plan (Volume 16, prompt 7; docs/PLAN_UPDATES.md): the preview
 * groups what's new by skill, one sentence each, with the rule for verdicts; a debugging exercise is
 * named as one and its verdict in the judge's terms, never a score; the version an update made lists
 * the code it read; the plan says which evidence it reads. */

const RULE = "How code counts: a pass counts as solved; failed tests, errors and time or memory limits count as tried, not solved. A verdict is never turned into a score.";
const ARRAYS = "Arrays: the debugging exercise “Fix: Coldest Reading” didn't pass (tests failed), which counts as tried, not solved, so the next version would suggest “Solve: Contains Duplicate” and not “Solve: Valid Palindrome”.";
const STRINGS = "Strings: “Valid Parentheses” didn't pass (compile error), which counts as tried, not solved, so the next version would suggest “Solve: Valid Parentheses”.";
const READS = "This plan reads your scored answers to Software Engineer questions, your finished question rounds and the lesson checks you've passed, and the judge's verdicts on code you submit: to problems, and to debugging exercises for the skills they name (not runs, which check the public tests only). A lesson only read, or a check not passed, isn't evidence. Improvements you accept are kept beside the plan and don't change what it suggests; the practice they lead to does.";

const NEWS: PlanNews = {
  text: "2 submissions (neither passed) since this plan.", answers: 0, retries: 0, below: 0, rounds: 0, submissions: 2, not_passed: 2, lessons: 0,
  entries: [
    { kind: "submission", title: "Fix: Coldest Reading", score: null, verdict: "not passed", verdict_detail: "tests failed", exercise: true, skill: "arrays", href: "/history/submissions/s-lab" },
    { kind: "submission", title: "Valid Parentheses", score: null, verdict: "not passed", verdict_detail: "compile error", exercise: false, skill: "strings", href: "/history/submissions/s-vp" },
  ],
  not_counted: ["1 submission the judge couldn't run isn’t counted: that was a problem on the judge's side, not your code."],
  by_skill: [{ skill: "arrays", count: 1, text: ARRAYS }, { skill: "strings", count: 1, text: STRINGS }],
  rule: RULE,
};

const engineer = (version: number, extra: Partial<Plan> = {}): Plan => ({
  ...makePlan(15), track: "software-engineer", career_title: "Software Engineer", version, evidence_read: READS, ...extra,
});

describe("Judged code as new evidence for the plan", () => {
  it("previews each skill in one sentence, says the rule and names an exercise with its verdict", async () => {
    let plan = engineer(1, { news: NEWS });
    const bodies: unknown[] = [];
    server.use(
      http.get(`${API}/api/v1/me/plan`, () => HttpResponse.json(plan)),
      http.post(`${API}/api/v1/me/plan/update`, async ({ request }) => {
        bodies.push(await request.json());
        plan = engineer(2, {
          news: null,
          changes: ["Updated when you asked: 2 submissions (neither passed) since version 1."],
          read_submissions: [
            { id: "s-lab", title: "Fix: Coldest Reading", verdict: "not passed", exercise: true, href: "/history/submissions/s-lab" },
            { id: "s-gone", title: null, verdict: null, exercise: false, href: null },
          ],
        });
        return HttpResponse.json(plan);
      }),
    );
    const { user } = renderApp("/plan", { signedIn: true });
    const news = await screen.findByRole("region", { name: /2 submissions \(neither passed\) since this plan\./ });
    expect(screen.getByText(READS)).toBeInTheDocument();
    const skills = within(news).getByRole("list", { name: "What it would change, by skill" });
    expect(within(skills).getAllByRole("listitem").map((li) => li.textContent)).toEqual([ARRAYS, STRINGS]);
    expect(news).toHaveTextContent(RULE);
    await user.click(within(news).getByText("What's new (2)"));
    const lab = within(news).getByRole("link", { name: "Debugging exercise: Fix: Coldest Reading" });
    expect(lab).toHaveAttribute("href", "/history/submissions/s-lab");
    expect(lab.parentElement).toHaveTextContent("· tests failed");
    expect(within(news).getByRole("link", { name: "Submission: Valid Parentheses" }).parentElement).toHaveTextContent("· compile error");
    expect(news).not.toHaveTextContent("/100"); // a verdict is never shown as a score
    expect(news).toHaveTextContent("that was a problem on the judge's side, not your code.");
    expect(bodies).toEqual([]); // the preview changes nothing

    await user.click(within(news).getByRole("button", { name: "Update my plan" }));
    const read = await screen.findByRole("list", { name: "Code this update read" });
    expect(within(read).getByRole("link", { name: "Debugging exercise: Fix: Coldest Reading" })).toHaveAttribute("href", "/history/submissions/s-lab");
    expect(read).toHaveTextContent("A submission that's no longer stored");
    expect(bodies).toEqual([{ version: 1, track: "software-engineer" }]);
  });

  it("a version from before lists no code it read", async () => {
    server.use(http.get(`${API}/api/v1/me/plan`, () => HttpResponse.json(engineer(3, { news: NEWS, read_submissions: null }))));
    renderApp("/plan", { signedIn: true });
    await screen.findByRole("region", { name: /2 submissions/ });
    expect(screen.queryByRole("list", { name: "Code this update read" })).not.toBeInTheDocument();
  });
});
