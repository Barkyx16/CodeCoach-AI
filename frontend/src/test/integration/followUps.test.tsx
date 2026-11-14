import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { FollowUpOut, InterviewAnswer } from "@/api/types";
import { nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

/**
 * Reviewed follow-up questions (Volume 12, prompt 4; docs/FOLLOW_UPS.md): offered after repeated
 * practice, worded conservatively, optional, and kept beside the original without merging scores.
 */
const URL = "/careers/registered-nurse/questions/m-pressure-0";
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: "registered-nurse" } }))));
const past: InterviewAnswer[] = [{ ...nurseAnswer, id: "a-2", created_at: "2026-11-14T11:00:00Z" }, { ...nurseAnswer, id: "a-1" }];
const out = (over: Partial<FollowUpOut> = {}): FollowUpOut => ({
  status: "offered", message: "An optional, different question about the same thing, to see whether what you practised carries over. Your answers here stay as they are.",
  threshold: 2, scored_answers: 2,
  offers: [{ track: "registered-nurse", question_id: "e-inform-2", title: "Keeping patients' families informed", version: 2,
    objective: "Keeping people informed through a normal day", difference: "Same communication habit, a different audience: patients' families instead of patients",
    exposure: "Not previously attempted in this app", attempts: 0 }],
  answered: [], ...over,
});

function setup(followUp: FollowUpOut) {
  asNurse();
  localStorage.clear();
  const asked = { n: 0 };
  server.use(
    http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json(past)),
    http.get(`${API}/api/v1/careers/:track/questions/:id/follow-up`, () => {
      asked.n += 1;
      return HttpResponse.json(followUp);
    }),
  );
  return asked;
}

const card = async () => (await screen.findByRole("heading", { name: "A related question" })).closest("section") as HTMLElement;

describe("A reviewed follow-up question", () => {
  it("is offered with what's the same, what's different and a careful exposure line", async () => {
    setup(out());
    renderApp(URL, { signedIn: true });
    const c = within(await card());
    const link = c.getByRole("link", { name: "Keeping patients' families informed" });
    expect(link).toHaveAttribute("href", "/careers/registered-nurse/questions/e-inform-2?followUpOf=a-2");
    expect(c.getByText("Version 2")).toBeInTheDocument();
    expect(c.getByText(/a different audience: patients' families/)).toBeInTheDocument();
    expect(c.getByText("Not previously attempted in this app.")).toBeInTheDocument();
    expect((await card()).textContent).not.toMatch(/new to you|never seen|mastered/i);
  });

  it("can be dismissed, and stays dismissed in this browser", async () => {
    const asked = setup(out());
    const { user, unmount } = renderApp(URL, { signedIn: true });
    await user.click(within(await card()).getByRole("button", { name: "Not now" }));
    await waitFor(() => expect(screen.queryByRole("heading", { name: "A related question" })).not.toBeInTheDocument());
    unmount();
    const before = asked.n;
    renderApp(URL, { signedIn: true });
    await screen.findByRole("heading", { name: "Your past answers" });
    await waitFor(() => expect(asked.n).toBeGreaterThan(before)); // the offer was read again
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("link", { name: "Keeping patients' families informed" })).not.toBeInTheDocument();
  });

  it("with no reviewed relationship, says so in one sentence", async () => {
    setup(out({ status: "none", message: "No reviewed related question is linked to this one yet.", offers: [] }));
    renderApp(URL, { signedIn: true });
    expect(within(await card()).getByText("No reviewed related question is linked to this one yet.")).toBeInTheDocument();
    expect(within(await card()).queryByRole("link")).not.toBeInTheDocument();
  });

  it("before the threshold, shows nothing", async () => {
    setup(out({ status: "not_yet", scored_answers: 1, offers: [], message: "After 2 answers…" }));
    renderApp(URL, { signedIn: true });
    await screen.findByRole("heading", { name: "Your past answers" });
    await waitFor(() => expect(screen.queryByRole("heading", { name: "A related question" })).not.toBeInTheDocument());
  });

  it("a follow-up answered is listed beside this question's answers with its own score and help", async () => {
    setup(out({ answered: [{ answer_id: "b-1", track: "registered-nurse", question_id: "e-inform-2", title: "Keeping patients' families informed",
      score: 61, rating: "Good start", evidence_level: "sufficient", content_version: 2, created_at: "2026-11-14T12:00:00Z", follows_up_answer_id: "a-2",
      conditions: { labels: ["No in-app help recorded"], help: [], recorded_from: "2026-11-14", note: "n" } }] }));
    renderApp(URL, { signedIn: true });
    const c = await card();
    const item = within(c).getAllByRole("link", { name: "Keeping patients' families informed" }).map((l) => l.closest("li")).find(Boolean)!;
    expect(item).toHaveTextContent("61/100 · Good start");
    expect(item).toHaveTextContent("version 2");
    expect(item).toHaveTextContent("In-app help: No in-app help recorded");
    expect(c.textContent).toMatch(/Scores aren't combined/);
    expect(c.textContent).not.toMatch(/average/i);
  });

  it("answering from the offer names the answer it follows, and says that one stays as it is", async () => {
    asNurse();
    let body: Record<string, unknown> | null = null;
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ ...nurseAnswer, id: "b-1", follows_up_answer_id: "a-2" }, { status: 201 });
    }));
    const { user } = renderApp(`${URL}?followUpOf=a-2`, { signedIn: true });
    expect(await screen.findByText(/A follow-up to your answer to a related question\. That answer stays as it is/)).toBeInTheDocument();
    await user.type(await screen.findByLabelText("Your answer"), "Each afternoon I call the family with the plan and what changed.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await waitFor(() => expect(body).not.toBeNull());
    expect(body).toMatchObject({ follows_up_answer_id: "a-2" });
  });
});
