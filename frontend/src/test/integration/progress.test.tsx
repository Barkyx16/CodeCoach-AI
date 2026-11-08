import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { nurseAnalytics, nurseAnswer, queuedSubmission, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));

describe("Unified History", () => {
  it("shows every career's activity with honest statuses and filters kept in the URL", async () => {
    const { user, router } = renderApp("/history", { signedIn: true });
    const list = await within(await screen.findByRole("main")).findByRole("list");
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByText("Scored 92/100 (Strong)")).toBeInTheDocument();
    expect(screen.getByText(/Saved, not judged \(the code judge isn't available/)).toBeInTheDocument();
    expect(screen.queryByText(/Passed/)).not.toBeInTheDocument();

    const skill = screen.getByLabelText("Skill");
    expect(skill).toBeDisabled(); // skills belong to one career
    // Career and activity options come from the facets request; wait for them, as a user would.
    await screen.findByRole("option", { name: "Registered Nurse (2)" });
    await user.selectOptions(screen.getByLabelText("Career"), "registered-nurse");
    expect(router.state.location.search).toBe("?career=registered-nurse");
    await waitFor(() => expect(within(within(screen.getByRole("main")).getByRole("list")).getAllByRole("listitem")).toHaveLength(2));
    expect(screen.getByLabelText("Skill")).toBeEnabled();
    await user.selectOptions(screen.getByLabelText("Activity"), "interview");
    expect(router.state.location.search).toBe("?career=registered-nurse&type=interview");
    expect(await screen.findByText("1 activity match")).toBeInTheDocument();
  });

  it("two filter changes in quick succession both stay (the second used to drop the first)", async () => {
    const { router } = renderApp("/history", { signedIn: true });
    await screen.findByRole("option", { name: "Registered Nurse (2)" });
    // Both before the page re-renders, as a fast hand (or a loaded machine) does.
    act(() => {
      fireEvent.change(screen.getByLabelText("Career"), { target: { value: "registered-nurse" } });
      fireEvent.change(screen.getByLabelText("Activity"), { target: { value: "interview" } });
    });
    await waitFor(() => expect(router.state.location.search).toBe("?career=registered-nurse&type=interview"));
  });

  it("opens an item and the in-app Back returns to the same filtered list", async () => {
    server.use(
      http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json([{ ...nurseAnswer, id: "a-1" }])),
    );
    asNurse();
    const { user, router } = renderApp("/history?career=registered-nurse&type=written_answer", { signedIn: true });
    await user.click(await screen.findByRole("link", { name: /What good patient assessment looks like/ }));
    expect(router.state.location.pathname).toBe("/careers/registered-nurse/questions/e-good-0");
    expect(router.state.location.search).toBe("?answer=a-1");
    // The linked answer's feedback opens on arrival.
    expect(await screen.findByRole("region", { name: /Feedback on try 1 from/ })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Back to History" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/history"));
    expect(router.state.location.search).toBe("?career=registered-nurse&type=written_answer");
    expect(screen.getByLabelText("Activity")).toHaveValue("written_answer");
  });

  it("a saved-but-unjudged submission says so, and its code never silently replaces a draft", async () => {
    server.use(http.get(`${API}/api/v1/submissions/:id`, () => HttpResponse.json({ ...queuedSubmission, source_code: "class Solution { /* old */ }" })));
    const { user, router } = renderApp("/history", { signedIn: true });
    await user.click(await screen.findByRole("link", { name: /Two Sum/ }));
    expect(await screen.findByRole("heading", { name: "Two Sum" })).toBeInTheDocument();
    expect(screen.getByText(/so this attempt was saved without a verdict/)).toBeInTheDocument();
    expect(screen.getByLabelText("Submitted code")).toHaveTextContent("class Solution { /* old */ }");
    await user.click(screen.getByRole("button", { name: "Open this code in the editor…" }));
    expect(router.state.location.pathname).toBe("/problems/two-sum");
    const offer = await screen.findByRole("region", { name: "Open past code" });
    expect(offer).toHaveTextContent("It replaces what's in the editor now");
    await user.click(within(offer).getByRole("button", { name: "Keep my draft" }));
    await waitFor(() => expect(screen.queryByRole("region", { name: "Open past code" })).not.toBeInTheDocument());
  });
});

describe("Career-aware Analytics", () => {
  it("shows a nurse's own analytics with definitions, gaps and an evaluator-specific trend", async () => {
    asNurse();
    renderApp("/analytics", { signedIn: true });
    expect(await screen.findByRole("region", { name: /Registered Nurse summary, last 90 days/ })).toBeInTheDocument();
    expect(screen.getByLabelText("Career")).toHaveValue("registered-nurse");
    expect(screen.queryByText(/Acceptance rate/)).not.toBeInTheDocument(); // no coding stats for nurses
    expect(screen.getByText("Not practised yet")).toBeInTheDocument(); // not shown as zero
    expect(screen.getByText(/Scored by built-in \(offline\) · rubric v1/)).toBeInTheDocument();
    expect(screen.getByText("1 ended early")).toBeInTheDocument();
    expect(screen.getByText("How these numbers are defined")).toBeInTheDocument();
  });

  it("lets you inspect another career without changing your career setting", async () => {
    let patched = false;
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: "barista" } }))),
      http.patch(`${API}/api/v1/auth/me`, () => { patched = true; return HttpResponse.json(baseUser); }),
    );
    const { user } = renderApp("/analytics", { signedIn: true });
    await screen.findByRole("option", { name: "Registered Nurse" });
    await user.selectOptions(screen.getByLabelText("Career"), "registered-nurse");
    expect(await screen.findByText(/Viewing Registered Nurse\. Your career setting is unchanged\./)).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: /Registered Nurse summary/ })).toBeInTheDocument();
    expect(patched).toBe(false);
  });

  it("explains how to create data when a career has none in the range", async () => {
    server.use(http.get(`${API}/api/v1/me/careers/:track/analytics`, () => HttpResponse.json({
      ...nurseAnalytics, answers: 0, questions_practiced: 0, strong_questions: 0, trends: [], by_day: [],
      interviews: { completed: 0, in_progress: 0, expired: 0, abandoned: 0 },
    })));
    asNurse();
    renderApp("/analytics?range=30", { signedIn: true });
    expect(await screen.findByText("No Registered Nurse practice in this range")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Answer a question" })).toBeInTheDocument();
  });
});

describe("Continue where you left off", () => {
  it("puts a running interview first, says its timer can't pause, and lists other saved work", async () => {
    window.localStorage.setItem("codecoach.answer.u-1.registered-nurse.e-good-0", "My unsent thoughts on assessment");
    window.localStorage.setItem("codecoach.draft.v1.u-1.two-sum", "class Solution { int x; }");
    server.use(http.get(`${API}/api/v1/me/resume`, () => HttpResponse.json({
      interview: { id: "round-3", kind: "questions", title: "Registered Nurse question round", deadline_at: new Date(Date.now() + 300_000).toISOString(), seconds_remaining: 300 },
      unfinished_problem: { slug: "two-sum", title: "Two Sum", last_status: "saved_not_judged", at: new Date().toISOString() },
      last_question: null,
    })));
    asNurse();
    const { user } = renderApp("/dashboard", { signedIn: true });
    const card = await screen.findByRole("region", { name: "Continue where you left off" });
    expect(within(card).getByText("Registered Nurse question round")).toBeInTheDocument();
    expect(within(card).getByText(/can't be paused/)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: /Resume interview/ })).toHaveAttribute("href", "/interviews/round-3");
    await user.click(within(card).getByText("Also saved (2)"));
    expect(await within(card).findByText(/An unsent answer \(5 words\) is saved in this browser/)).toBeInTheDocument();
    expect(within(card).getByText(/Your code draft is saved in this browser/)).toBeInTheDocument();
  });

  it("stays hidden when there's nothing saved", async () => {
    asNurse();
    renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByText("Registered Nurse · Easy level")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("region", { name: "Continue where you left off" })).not.toBeInTheDocument());
  });
});
