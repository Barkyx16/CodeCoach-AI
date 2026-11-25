import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { nurseAnswer, nurseQuestions, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

// An answered question whose answers were all too short to score has no score: it's offered again,
// never shown by its capped stored number (Durable Saves brief 08). Synthetic data only.

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const tooShort = { ...nurseQuestions[0]!, best_score: 30, best_scored: null, score_status: "too_short" as const };

function withQuestions() {
  const items = [tooShort, ...nurseQuestions.slice(1)];
  server.use(
    http.get(`${API}/api/v1/careers/:track/questions`, ({ request }) => {
      const difficulty = new URL(request.url).searchParams.get("difficulty");
      const list = items.filter((x) => !difficulty || x.difficulty === difficulty);
      return HttpResponse.json({ items: list, total: list.length, page: 1, page_size: 100 });
    }),
    http.get(`${API}/api/v1/careers/:track/questions/:id`, ({ params }) =>
      params.id === tooShort.id
        ? HttpResponse.json({ ...tooShort, track: "registered-nurse", career_title: "Registered Nurse", tips: [], rubric_labels: [] })
        : HttpResponse.json({ error: { code: "not_found", message: "x", request_id: "r", details: null } }, { status: 404 })),
  );
}

describe("A question answered only too briefly", () => {
  it("is offered again on the dashboard, without its capped number", async () => {
    asNurse();
    withQuestions();
    renderApp("/dashboard", { signedIn: true });
    const link = await screen.findByRole("link", { name: new RegExp(tooShort.title) });
    expect(within(link).getByText("Try again")).toBeInTheDocument();
    expect(link).toHaveTextContent("Your answers here were too short to score.");
    expect(link).not.toHaveTextContent(/30/);
  });

  it("says so on its page instead of showing a best score", async () => {
    asNurse();
    withQuestions();
    renderApp(`/careers/registered-nurse/questions/${tooShort.id}`, { signedIn: true });
    expect(await screen.findByText("Answered, too short to score")).toBeInTheDocument();
    expect(screen.queryByText(/Best score/)).not.toBeInTheDocument();
  });

  it("lists an answer whose grading wasn't recorded as not counted, and won't compare it", async () => {
    // Release Readiness brief 02: the server says evidence_level "unknown" for such a row.
    asNurse();
    withQuestions();
    server.use(http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json([
      { ...nurseAnswer, id: "u1", question_id: tooShort.id, score: 50, evidence_level: "unknown", created_at: "2026-11-01T09:00:00Z" },
    ])));
    const { user } = renderApp(`/careers/registered-nurse/questions/${tooShort.id}`, { signedIn: true });
    const entry = await screen.findByRole("button", { name: /not counted \(how it was graded wasn't recorded\)/ });
    await user.click(entry);
    expect(await screen.findByText(/its score isn't counted in your best scores or averages/)).toBeInTheDocument();
    expect(screen.getByLabelText(/how it was graded wasn't recorded, so it isn't counted/)).toBeInTheDocument();
  });
});
