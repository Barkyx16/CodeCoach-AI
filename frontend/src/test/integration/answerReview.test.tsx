import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { AnswerReview, Criteria, InterviewAnswer } from "@/api/types";

import { nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const URL = "/careers/registered-nurse/questions/m-pressure-0";
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: "registered-nurse" } }))));

const criteria: Criteria = {
  question_id: "m-pressure-0", content_version: 1, rubric_version: "v1", coach: "built-in (offline)",
  criteria: [
    { label: "Sets the scene: where you were and what was at stake", description: "Open with context.", levels: [{ level: "not_yet", text: "Not yet: Open with context." }, { level: "there", text: "There: sets the scene, in your own words." }] },
    { label: "Shares a result, ideally with a number", description: "Finish with what happened.", levels: [{ level: "not_yet", text: "Not yet: Finish with what happened." }, { level: "there", text: "There: shares a result, in your own words." }] },
  ],
  checks: [{ kind: "deterministic", text: "Length: about 120 to 350 words reads like a one-to-two-minute spoken answer." }],
  disclaimer: "These are CodeCoach's practice criteria for this question, not an employer's rubric.",
};

const answer: InterviewAnswer = {
  ...nurseAnswer, rubric_version: "v1", evidence_level: "sufficient",
  points: [
    { label: criteria.criteria[0]!.label, covered: true, advice: "Open with context.", evidence: "Last winter, on nights, a patient's oxygen dropped." },
    { label: criteria.criteria[1]!.label, covered: false, advice: "Finish with what happened.", evidence: null },
  ],
};

function review(over: Partial<AnswerReview> = {}): AnswerReview {
  return {
    answer, self_review: null, perspectives: answer.points.map((p) => ({ criterion: p.label, yours: null, coach: p.covered })), repeated: [], flags: [], evaluations: [],
    can_reevaluate: false, reevaluate_note: "The built-in coach gives the same result for the same answer under the same rubric and question version.", ...over,
  };
}

function setup(a: InterviewAnswer = answer) {
  asNurse();
  localStorage.clear();
  server.use(
    http.get(`${API}/api/v1/careers/registered-nurse/questions/m-pressure-0/criteria`, () => HttpResponse.json(criteria)),
    http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json(a, { status: 201 })),
  );
}

describe("rubric transparency and self-review", () => {
  it("shows the criteria before answering, with fixed checks labelled apart, and quotes evidence after", async () => {
    setup();
    const { user } = renderApp(URL, { signedIn: true });
    await screen.findByRole("heading", { level: 1, name: "Patient assessment under pressure" });
    await user.click(await screen.findByText("How your answer is evaluated"));
    expect(screen.getByText("Not yet: Finish with what happened.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Fixed checks, the same for every answer" })).toBeInTheDocument();
    expect(screen.getByText(/not an employer's rubric/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your answer"), "Last winter, on nights, a patient's oxygen dropped.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    const fb = await screen.findByRole("region", { name: "Feedback" });
    expect(within(fb).getByText("“Last winter, on nights, a patient's oxygen dropped.”")).toBeInTheDocument();
    expect(within(fb).getByText(/rubric v1/)).toBeInTheDocument();
  });

  it("shows 'not enough to score' instead of a number for an answer too short to evaluate", async () => {
    setup({ ...answer, score: 35, rating: "Needs work", evidence_level: "insufficient", summary: "Too short to be convincing yet (9 words)." });
    const { user } = renderApp(URL, { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "I called the team and stayed with him.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    const fb = await screen.findByRole("region", { name: "Feedback" });
    expect(within(fb).getByLabelText("Not enough to score yet")).toBeInTheDocument();
    expect(within(fb).queryByText("35")).not.toBeInTheDocument();
  });

  it("can hold the feedback for an optional reflection, skipped without penalty or saved beside the result", async () => {
    setup();
    let saved: Record<string, unknown> | null = null;
    server.use(
      http.put(`${API}/api/v1/me/answers/a-1/self-review`, async ({ request }) => {
        saved = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(review());
      }),
      http.get(`${API}/api/v1/me/answers/a-1/review`, () => HttpResponse.json(review({
        self_review: { went_well: "Calm opening", improve: "Say the result", ratings: { [answer.points[1]!.label]: "yes" }, skipped: false, before_feedback: true, updated_at: "2026-11-03T10:00:00Z" },
        perspectives: [{ criterion: answer.points[0]!.label, yours: null, coach: true }, { criterion: answer.points[1]!.label, yours: "yes", coach: false }],
      }))),
    );
    const { user } = renderApp(URL, { signedIn: true });
    await user.click(await screen.findByRole("checkbox", { name: /Reflect on my answer before seeing the feedback/ }));
    await user.type(screen.getByLabelText("Your answer"), "Last winter, on nights, a patient's oxygen dropped.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    const gate = await screen.findByRole("form", { name: "Before you read the feedback" });
    expect(screen.queryByRole("region", { name: "Feedback" })).not.toBeInTheDocument(); // held, not withheld for good
    await user.type(within(gate).getByLabelText("What went well?"), "Calm opening");
    await user.click(within(within(gate).getByRole("radiogroup", { name: answer.points[1]!.label })).getByRole("radio", { name: "Yes" }));
    await user.click(within(gate).getByRole("button", { name: "Save and show feedback" }));
    expect(await screen.findByRole("region", { name: "Feedback" })).toBeInTheDocument();
    expect(saved).toMatchObject({ went_well: "Calm opening", ratings: { [answer.points[1]!.label]: "yes" }, skipped: false, before_feedback: true });
    const table = await screen.findByRole("table", { name: "Your ratings beside what the coach found" });
    expect(within(table).getAllByRole("row")[2]).toHaveTextContent(/Yes.*Not found/);
    expect(screen.getByText(/Neither view proves the other right/)).toBeInTheDocument();
  });

  it("skipping shows the feedback straight away", async () => {
    setup();
    let body: Record<string, unknown> | null = null;
    server.use(http.put(`${API}/api/v1/me/answers/a-1/self-review`, async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(review());
    }));
    localStorage.setItem("codecoach.reflect-first", "on");
    const { user } = renderApp(URL, { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Last winter, on nights, a patient's oxygen dropped.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await user.click(await screen.findByRole("button", { name: "Skip and show feedback" }));
    expect(await screen.findByRole("region", { name: "Feedback" })).toBeInTheDocument();
    await waitFor(() => expect(body).toMatchObject({ skipped: true }));
  });

  it("flags a criterion privately and explains why checking again wouldn't change anything", async () => {
    setup();
    let flagged: Record<string, unknown> | null = null;
    server.use(
      http.get(`${API}/api/v1/me/answers/a-1/review`, () => HttpResponse.json(review())),
      http.post(`${API}/api/v1/me/answers/a-1/flags`, async ({ request }) => {
        flagged = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(review({ flags: [{ id: 1, criterion: answer.points[1]!.label, kind: "disagree", note: "I did say the result.", created_at: "2026-11-03T10:00:00Z", disputed: true, disputed_at: "2026-11-03T10:00:00Z", reinstated_at: null }] }));
      }),
    );
    const { user } = renderApp(URL, { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Last winter, on nights, a patient's oxygen dropped.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await user.click(await screen.findByText("Your reflection, flags and checking again"));
    expect(await screen.findByText(/same result for the same answer/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Check again with the current rubric" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: `Flag “${answer.points[1]!.label}”` }));
    await user.click(screen.getByRole("radio", { name: "I disagree" }));
    await user.type(screen.getByLabelText("Private note (optional)"), "I did say the result.");
    await user.click(screen.getByRole("button", { name: "Save flag" }));
    expect(await screen.findByText("You disagree")).toBeInTheDocument();
    expect(flagged).toEqual({ criterion: answer.points[1]!.label, kind: "disagree", note: "I did say the result." });
  });

  it("says what disagreeing does, and counting the point in the plan again is a deliberate, recorded button", async () => {
    setup();
    const label = answer.points[1]!.label;
    const flagged = { id: 7, criterion: label, kind: "disagree" as const, note: "I did say the result.", created_at: "2026-11-03T10:00:00Z", disputed: true, disputed_at: "2026-11-03T10:00:00Z", reinstated_at: null };
    let reinstated = 0;
    server.use(
      http.get(`${API}/api/v1/me/answers/a-1/review`, () => HttpResponse.json(review({ flags: [flagged] }))),
      http.post(`${API}/api/v1/me/answers/a-1/flags/7/reinstate`, () => {
        reinstated += 1;
        return HttpResponse.json(review({ flags: [{ ...flagged, disputed: false, reinstated_at: "2026-11-05T09:00:00Z" }] }));
      }),
    );
    const { user } = renderApp(URL, { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Last winter, on nights, a patient's oxygen dropped.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await user.click(await screen.findByText("Your reflection, flags and checking again"));
    expect(await screen.findByText("You disagree")).toBeInTheDocument();
    expect(screen.getByText(/"I disagree" keeps that point out of your automatic plan until you count it again; your score and the feedback don't change\./)).toBeInTheDocument();
    expect(screen.getByText(/Disputed on 3 November: this point doesn't shape your plan until you count it again\./)).toBeInTheDocument();
    expect(reinstated).toBe(0); // nothing counts it again by itself
    await user.click(screen.getByRole("button", { name: "Count it in my plan again" }));
    expect(await screen.findByText(/Counted in your plan again since 5 November\./)).toBeInTheDocument();
    expect(screen.getByText("You disagreed")).toBeInTheDocument();
    expect(screen.getByText(/I did say the result\./)).toBeInTheDocument(); // the flag and its note stay
    expect(screen.queryByRole("button", { name: "Count it in my plan again" })).not.toBeInTheDocument();
    expect(reinstated).toBe(1);
    expect(within(screen.getByRole("region", { name: "Feedback" })).getByLabelText("Score 92 out of 100, Strong")).toBeInTheDocument(); // unchanged
  });

  it("records a second evaluation beside the original when the rubric changed", async () => {
    setup();
    server.use(
      http.get(`${API}/api/v1/me/answers/a-1/review`, () => HttpResponse.json(review({ can_reevaluate: true, reevaluate_note: "The question or the rubric changed since this answer was checked." }))),
      http.post(`${API}/api/v1/me/answers/a-1/evaluations`, () => HttpResponse.json(review({
        evaluations: [{ id: 1, rubric_version: "v2", content_version: 2, score: 70, rating: "Good", summary: "Solid. One thing to add: a result.", evidence_level: "sufficient", points: [], reason: "", created_at: "2026-11-03T11:00:00Z" }],
      }))),
    );
    const { user } = renderApp(URL, { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Last winter, on nights, a patient's oxygen dropped.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await user.click(await screen.findByText("Your reflection, flags and checking again"));
    await user.click(await screen.findByRole("button", { name: "Check again with the current rubric" }));
    expect(await screen.findByText(/Original: score 92 \(Strong\), rubric v1, question version 1\. Kept as it was\./)).toBeInTheDocument();
    expect(screen.getByText(/score 70 \(Good\), rubric v2, question version 2/)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Feedback" })).getByLabelText("Score 92 out of 100, Strong")).toBeInTheDocument();
  });
});
