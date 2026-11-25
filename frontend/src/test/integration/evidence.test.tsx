import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { InterviewAnswer } from "@/api/types";

import { nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

// The evidence contract on the page (Volume 4 prompt 06): a checked quote can be found in the
// answer it reviewed, older quotes are labelled, a quote that couldn't be checked isn't shown, and
// a changed draft is never presented as what was reviewed.

const nurse = { ...baseUser, career_track: "registered-nurse" };
const QUESTION = "/careers/registered-nurse/questions/m-pressure-0";
// An emoji (two UTF-16 code units, as JavaScript counts) before the quote: the span is in those units.
const ANSWER = "🏥 Last winter on a night shift, I called the rapid response team and started oxygen. He was stable within 30 minutes.";
const QUOTE = "I called the rapid response team and started oxygen.";

function answered(points: InterviewAnswer["points"]): InterviewAnswer {
  return { ...nurseAnswer, answer: ANSWER, points };
}

function setUp(answer: InterviewAnswer) {
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json([])),
    http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json(answer, { status: 201 })),
  );
}

async function send(user: ReturnType<typeof renderApp>["user"]) {
  await user.type(await screen.findByLabelText("Your answer"), "Last winter I handled a deteriorating patient.");
  await user.click(screen.getByRole("button", { name: "Get feedback" }));
  return screen.findByRole("region", { name: "Feedback" });
}

describe("Feedback evidence", () => {
  it("a checked quote opens the answer it came from, marked at its place, with focus on it", async () => {
    const start = ANSWER.indexOf(QUOTE); // JavaScript's own offsets: UTF-16 code units
    setUp(answered([
      { label: "Describes specific actions you took", covered: true, advice: "a", evidence: QUOTE, span: [start, start + QUOTE.length], evidence_status: "verified" },
      { label: "Shares a result, ideally with a number", covered: false, advice: "Finish with what happened." },
    ]));
    const { user } = renderApp(QUESTION, { signedIn: true });
    const feedback = await send(user);
    expect(within(feedback).getByText(/Fixed checks on how your answer is built/)).toBeInTheDocument();
    await user.click(within(feedback).getByRole("button", { name: /Show it in your answer: Describes specific actions you took/ }));
    const mark = await waitFor(() => {
      const m = feedback.querySelector("mark");
      if (!m) throw new Error("not marked yet");
      return m;
    });
    expect(mark).toHaveTextContent(QUOTE);
    await waitFor(() => expect(mark).toHaveFocus());
    expect(within(feedback).getByText(/The answer this feedback is for/).closest("details")).toHaveAttribute("open");
  });

  it("an older quote is labelled and has no place to show; a quote that couldn't be checked isn't shown", async () => {
    setUp(answered([
      { label: "Describes specific actions you took", covered: true, advice: "a", evidence: QUOTE, span: null, evidence_status: "legacy" },
      { label: "Sets the scene: where you were and what was at stake", covered: true, advice: "a", evidence: null, span: null, evidence_status: "omitted" },
    ]));
    const { user } = renderApp(QUESTION, { signedIn: true });
    const feedback = await send(user);
    expect(within(feedback).getByText(/older feedback: where it was isn't recorded/)).toBeInTheDocument();
    expect(within(feedback).queryByRole("button", { name: /Show it in your answer/ })).not.toBeInTheDocument();
    expect(within(feedback).getByText(/the quote couldn't be checked against it, so it isn't shown/)).toBeInTheDocument();
  });

  it("a span that doesn't fit the answer is never used to mark it", async () => {
    setUp(answered([
      { label: "Describes specific actions you took", covered: true, advice: "a", evidence: QUOTE, span: [5, 9_999], evidence_status: "verified" },
    ]));
    const { user } = renderApp(QUESTION, { signedIn: true });
    const feedback = await send(user);
    expect(within(feedback).queryByRole("button", { name: /Show it in your answer/ })).not.toBeInTheDocument();
  });

  it("says when the answer box no longer holds the version that was reviewed", async () => {
    setUp(answered([{ label: "Describes specific actions you took", covered: false, advice: "a" }]));
    const { user } = renderApp(QUESTION, { signedIn: true });
    const feedback = await send(user);
    expect(within(feedback).queryByText(/You've changed your answer since/)).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Your answer"), "A new draft about a different night.");
    expect(within(feedback).getByText(/You've changed your answer since/)).toBeInTheDocument();
    expect(within(feedback).getByText("The answer this feedback is for")).toBeInTheDocument();
  });
});
