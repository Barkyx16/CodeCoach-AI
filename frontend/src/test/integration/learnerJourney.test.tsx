import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { InterviewAnswer } from "@/api/types";

import { nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

// The learner journey from choosing practice to what comes after feedback (Learner Experience
// pack). Synthetic accounts and answers only.

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));

describe("A link to a question that isn't there", () => {
  it("says the question isn't available and leads back to that career's questions, without a retry that can't help", async () => {
    asNurse();
    renderApp("/careers/registered-nurse/questions/no-such-question", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "This question isn't available" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Browse Registered Nurse questions" })).toHaveAttribute("href", "/problems?view=questions");
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("for another career, the way back keeps that career", async () => {
    asNurse();
    renderApp("/careers/barista/questions/no-such-question", { signedIn: true });
    expect(await screen.findByRole("link", { name: "Browse Barista questions" })).toHaveAttribute("href", "/problems?career=barista&view=questions");
  });

  it("an unknown career leads to the question library", async () => {
    server.use(http.get(`${API}/api/v1/careers/:track/questions/:id`, () =>
      HttpResponse.json({ error: { code: "not_found", message: "Career 'x' not found", request_id: "r", details: null } }, { status: 404 })));
    asNurse();
    renderApp("/careers/no-such-career/questions/e-good-0", { signedIn: true });
    expect(await screen.findByRole("link", { name: "Browse interview questions" })).toHaveAttribute("href", "/problems?view=questions");
  });

  it("a server failure is still offered a retry (it may be temporary)", async () => {
    server.use(http.get(`${API}/api/v1/careers/:track/questions/:id`, () =>
      HttpResponse.json({ error: { code: "internal_error", message: "Something went wrong.", request_id: "r", details: null } }, { status: 500 })));
    asNurse();
    renderApp("/careers/registered-nurse/questions/e-good-0", { signedIn: true });
    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("a coding problem that isn't there leads back to the problems, without a retry", async () => {
    server.use(http.get(`${API}/api/v1/problems/:slug`, () =>
      HttpResponse.json({ error: { code: "not_found", message: "Problem not found", request_id: "r", details: null } }, { status: 404 })));
    renderApp("/problems/no-such-problem", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "This problem isn't available" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse coding problems" })).toHaveAttribute("href", "/problems");
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });
});

const SCENE = "Sets the scene: where you were and what was at stake";
const RESULT = "Shares a result, ideally with a number";
const FIRST_TEXT = "Last winter on a busy ward I noticed a patient's breathing change, checked their observations and called the doctor.";

function tryAt(id: string, at: string, result: boolean, extra: Partial<InterviewAnswer> = {}): InterviewAnswer {
  return {
    ...nurseAnswer, id, question_id: "e-good-0", created_at: at,
    points: [
      { label: SCENE, covered: true, advice: "Open with context.", evidence: "Last winter on a busy ward", evidence_status: "legacy" },
      { label: RESULT, covered: result, advice: "Finish with what happened." },
    ],
    ...extra,
  };
}
const try1 = tryAt("t1", "2026-11-01T09:00:00Z", false, { answer: FIRST_TEXT, score: 58, rating: "Good start" });
const try2 = tryAt("t2", "2026-11-02T09:00:00Z", true, { answer: `${FIRST_TEXT} Their oxygen was back to 96% within the hour.`, score: 81, rating: "Good" });
const listAnswers = (items: InterviewAnswer[]) =>
  server.use(http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json(items)));
const sidebar = () => screen.getByRole("heading", { name: "Your past answers" }).closest("section, .card") as HTMLElement;

describe("Past answers keep their identity", () => {
  it("each is numbered from the first, opens under its own title, and is kept in the URL", async () => {
    asNurse();
    listAnswers([try2, try1]);
    const { user, router } = renderApp("/careers/registered-nurse/questions/e-good-0", { signedIn: true });
    const first = await screen.findByRole("button", { name: /Try 1 \(first\)/ });
    expect(within(sidebar()).getByRole("button", { name: /Try 2/ })).toHaveTextContent("81/100 · Good");
    await user.click(first);
    expect(router.state.location.search).toBe("?answer=t1");
    // An earlier answer is never titled as if it had just been sent.
    expect(await screen.findByRole("region", { name: /^Feedback on try 1 from/ })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Feedback" })).not.toBeInTheDocument();
    expect(first).toHaveAttribute("aria-pressed", "true");
  });

  it("an answer too short to score is listed as such, not by its capped number", async () => {
    asNurse();
    listAnswers([tryAt("short", "2026-11-03T09:00:00Z", false, { score: 20, evidence_level: "insufficient", word_count: 6 }), try1]);
    renderApp("/careers/registered-nurse/questions/e-good-0", { signedIn: true });
    expect(await screen.findByRole("button", { name: /Try 2/ })).toHaveTextContent("Too short to score");
    expect(within(sidebar()).queryByText(/20\/100/)).not.toBeInTheDocument();
  });
});

describe("What next, after feedback", () => {
  it("says what this try covered and compares it with the one before when both were graded the same way", async () => {
    asNurse();
    listAnswers([try2, try1]);
    const { user } = renderApp("/careers/registered-nurse/questions/e-good-0?answer=t2", { signedIn: true });
    const recap = await screen.findByRole("region", { name: "What next" });
    expect(recap).toHaveTextContent("Try 2 covered all 2 points the rubric looks for.");
    expect(recap).toHaveTextContent(`Compared with try 1 (same question version, rubric and coach): now covers “${RESULT}”; score 58, now 81.`);
    await user.click(within(sidebar()).getByRole("button", { name: /Try 1/ }));
    expect(await screen.findByRole("region", { name: "What next" })).toHaveTextContent(`Try 1 covered 1 of 2 points the rubric looks for. To add: “${RESULT}”.`);
  });

  it("says plainly when two comparable tries cover the same points with the same score", async () => {
    asNurse();
    listAnswers([{ ...try2, points: try1.points, score: 58 }, try1]);
    renderApp("/careers/registered-nurse/questions/e-good-0?answer=t2", { signedIn: true });
    expect(await screen.findByRole("region", { name: "What next" }))
      .toHaveTextContent("Compared with try 1 (same question version, rubric and coach): covers the same points; score 58 both times.");
  });

  it("doesn't compare tries graded with different rubrics, and says why", async () => {
    asNurse();
    listAnswers([{ ...try2, rubric_version: "v8" }, { ...try1, rubric_version: "v5" }]);
    renderApp("/careers/registered-nurse/questions/e-good-0?answer=t2", { signedIn: true });
    const recap = await screen.findByRole("region", { name: "What next" });
    expect(recap).toHaveTextContent("Not directly comparable with try 1: they were graded with different rubrics (v5 and v8).");
    expect(recap).not.toHaveTextContent(/score 58, now 81/);
    expect(within(sidebar()).getByText(/graded with different rubric versions/)).toBeInTheDocument();
  });

  it("offers the next unanswered question at this level, or says there isn't one", async () => {
    asNurse();
    listAnswers([{ ...try2, question_id: "e-time-0" }]);
    renderApp("/careers/registered-nurse/questions/e-time-0?answer=t2", { signedIn: true });
    expect(await screen.findByRole("link", { name: "Next question: What good patient assessment looks like" }))
      .toHaveAttribute("href", "/careers/registered-nurse/questions/e-good-0");
  });

  it("with no unanswered question left at this level, points to the library instead", async () => {
    asNurse();
    listAnswers([try2]);
    renderApp("/careers/registered-nurse/questions/e-good-0?answer=t2", { signedIn: true });
    const recap = await screen.findByRole("region", { name: "What next" });
    expect(await within(recap).findByText(/Every other easy question here has an answer/)).toBeInTheDocument();
    expect(within(recap).getByRole("link", { name: "Back to Registered Nurse questions" })).toHaveAttribute("href", "/problems?view=questions");
  });
});

describe("A revision aimed at one missing point", () => {
  it("starts from the earlier answer, names the point, can start blank with an undo, and saves a new try", async () => {
    asNurse();
    listAnswers([try1]);
    let posted: unknown = null;
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, async ({ request }) => {
      posted = await request.json();
      return HttpResponse.json(tryAt("t-new", new Date().toISOString(), true, { answer: (posted as { answer: string }).answer, score: 80 }), { status: 201 });
    }));
    const { user } = renderApp("/careers/registered-nurse/questions/e-good-0?answer=t1", { signedIn: true });
    const recap = await screen.findByRole("region", { name: "What next" });
    await user.click(within(recap).getByRole("button", { name: "Revise this answer" }));
    const box = screen.getByRole("textbox", { name: "Your answer" });
    expect(box).toHaveValue(FIRST_TEXT);
    await waitFor(() => expect(box).toHaveFocus());
    expect(screen.getByText(`Revising try 1: add “${RESULT}”.`)).toBeInTheDocument();
    expect(screen.getByText(/Describe only what really happened/)).toBeInTheDocument();

    // Starting blank can be undone (nothing is lost by one click).
    await user.click(screen.getByRole("button", { name: "Start from a blank box" }));
    expect(box).toHaveValue("");
    await user.click(screen.getByRole("button", { name: "Undo" }));
    expect(box).toHaveValue(FIRST_TEXT);

    await user.type(box, " Her oxygen was back to 96% within the hour.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await waitFor(() => expect(posted).toEqual({ answer: `${FIRST_TEXT} Her oxygen was back to 96% within the hour.` }));
    // The new try is shown as new; the first stays listed as it was.
    expect(await screen.findByRole("region", { name: "Feedback" })).toBeInTheDocument();
    expect(screen.queryByText(/Revising try 1/)).not.toBeInTheDocument();
    expect(within(sidebar()).getByRole("button", { name: /Try 1 \(first\)/ })).toHaveTextContent("58/100");
  });

  it("never replaces text the learner hasn't sent", async () => {
    asNurse();
    listAnswers([try1]);
    const { user } = renderApp("/careers/registered-nurse/questions/e-good-0?answer=t1", { signedIn: true });
    const box = await screen.findByRole("textbox", { name: "Your answer" });
    await user.type(box, "A different start I was writing");
    await user.click(within(await screen.findByRole("region", { name: "What next" })).getByRole("button", { name: "Revise this answer" }));
    expect(box).toHaveValue("A different start I was writing");
    expect(screen.getByText(/Your unsent text is still in the box/)).toBeInTheDocument();
  });

  it("isn't offered while offline (feedback needs a connection)", async () => {
    asNurse();
    listAnswers([try1]);
    renderApp("/careers/registered-nurse/questions/e-good-0?answer=t1", { signedIn: true });
    const recap = await screen.findByRole("region", { name: "What next" });
    expect(within(recap).getByRole("button", { name: "Revise this answer" })).toBeInTheDocument();
    window.dispatchEvent(new Event("offline"));
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
    window.dispatchEvent(new Event("offline"));
    await waitFor(() => expect(within(recap).queryByRole("button", { name: "Revise this answer" })).not.toBeInTheDocument());
    Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
    window.dispatchEvent(new Event("online"));
  });
});

describe("The list a question was opened from", () => {
  it("the breadcrumb returns to the filtered list, also after moving on to the next question", async () => {
    asNurse();
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, () =>
      HttpResponse.json({ ...try1, id: "t-sent", question_id: "e-time-0", created_at: new Date().toISOString() }, { status: 201 })));
    const { user, router } = renderApp("/problems?view=questions&q=assessment", { signedIn: true });
    await user.click(await screen.findByRole("link", { name: /A time patient assessment mattered/ }));
    const crumb = () => within(screen.getByRole("navigation", { name: "Breadcrumb" })).getByRole("link");
    expect(await screen.findByRole("heading", { level: 1, name: "A time patient assessment mattered" })).toBeInTheDocument();
    expect(crumb()).toHaveAttribute("href", "/problems?view=questions&q=assessment");

    await user.type(screen.getByRole("textbox", { name: "Your answer" }), "Last winter I noticed a change and acted on it.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await user.click(await screen.findByRole("link", { name: "Next question: What good patient assessment looks like" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/careers/registered-nurse/questions/e-good-0"));
    expect(await screen.findByRole("heading", { level: 1, name: "What good patient assessment looks like" })).toBeInTheDocument();
    expect(crumb()).toHaveAttribute("href", "/problems?view=questions&q=assessment");
  });

  it("ignores anything but the library's own paths in that state", async () => {
    asNurse();
    const { router } = renderApp("/problems", { signedIn: true });
    await router.navigate("/careers/registered-nurse/questions/e-good-0", { state: { listFrom: "https://example.com/x" } });
    expect(await screen.findByRole("heading", { level: 1, name: "What good patient assessment looks like" })).toBeInTheDocument();
    expect(within(screen.getByRole("navigation", { name: "Breadcrumb" })).getByRole("link")).toHaveAttribute("href", "/problems?view=questions");
  });
});

describe("Sending an answer when no reply comes back", () => {
  it("finds it among the saved answers when the server did save it, instead of asking to send it twice", async () => {
    asNurse();
    const saved: InterviewAnswer[] = [];
    let posts = 0;
    server.use(
      http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, async ({ request }) => {
        posts += 1;
        const { answer } = (await request.json()) as { answer: string };
        saved.unshift({ ...try2, id: "t-saved", answer, created_at: new Date().toISOString() });
        return HttpResponse.error(); // saved, but the reply is lost
      }),
      http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json(saved)),
    );
    const { user } = renderApp("/careers/registered-nurse/questions/e-good-0", { signedIn: true });
    const box = await screen.findByRole("textbox", { name: "Your answer" });
    await user.type(box, "Last winter I noticed a change and acted on it.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    expect(await screen.findByRole("region", { name: "Feedback" })).toBeInTheDocument();
    expect(box).toHaveValue("");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/isn't certain whether this answer was saved/)).not.toBeInTheDocument();
    expect(posts).toBe(1);
  });

  it("says the outcome is unknown and keeps the text when it isn't among the saved answers", async () => {
    asNurse();
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.error()));
    const { user } = renderApp("/careers/registered-nurse/questions/e-good-0", { signedIn: true });
    const box = await screen.findByRole("textbox", { name: "Your answer" });
    await user.type(box, "Last winter I noticed a change and acted on it.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    expect(await screen.findByText(/isn't certain whether this answer was saved/)).toBeInTheDocument();
    expect(box).toHaveValue("Last winter I noticed a change and acted on it.");
    expect(screen.queryByRole("region", { name: "Feedback" })).not.toBeInTheDocument();
  });

  it("a definite refusal (the server answered) isn't treated as unknown", async () => {
    asNurse();
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, () =>
      HttpResponse.json({ error: { code: "unavailable", message: "The server is busy. Try again.", request_id: "r", details: null } }, { status: 503 })));
    const { user } = renderApp("/careers/registered-nurse/questions/e-good-0", { signedIn: true });
    await user.type(await screen.findByRole("textbox", { name: "Your answer" }), "Last winter I noticed a change.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The server is busy. Try again.");
    expect(screen.queryByText(/isn't certain whether/)).not.toBeInTheDocument();
  });
});
