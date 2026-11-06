import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { InterviewAnswer } from "@/api/types";

import { nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

// A career whose written-answer feedback hasn't been measured says so plainly, and a point that
// sounds like a correctness judgement says what it really checks (Volume 4 prompt 10).

const nurse = { ...baseUser, career_track: "registered-nurse" };

function setUp(answer: InterviewAnswer) {
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json([])),
    http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json(answer, { status: 201 })),
  );
}

async function send(user: ReturnType<typeof renderApp>["user"]) {
  await user.type(await screen.findByLabelText("Your answer"), "Last winter I handled a difficult call.");
  await user.click(screen.getByRole("button", { name: "Get feedback" }));
  return screen.findByRole("region", { name: "Feedback" });
}

describe("Career scope in feedback", () => {
  it("an unmeasured career's feedback carries a visible note, and a domain-sounding point says what it checks", async () => {
    setUp({
      ...nurseAnswer,
      track: "electrician",
      evaluation_status: "not_measured",
      evaluation_note: "These are general interview-structure checks; they haven't been measured on Electrician answers.",
      points: [
        { label: "Explains ticket backlogs correctly", covered: true, advice: "a", scope_note: "Checks that you discuss it, not whether what you say is right." },
      ],
    });
    const { user } = renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    const feedback = await send(user);
    expect(within(feedback).getByText(/haven't been measured on Electrician answers/)).toHaveClass("banner");
    expect(within(feedback).getByText("Checks that you discuss it, not whether what you say is right.")).toBeInTheDocument();
  });

  it("a measured career's note is quiet", async () => {
    setUp(nurseAnswer);
    const { user } = renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    const feedback = await send(user);
    expect(within(feedback).getByText(/checked against example answers written for it/)).not.toHaveClass("banner");
  });
});
