import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { AttemptConditions, InterviewAnswer } from "@/api/types";
import { activityItems, nurseAnswer, queuedSubmission, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

/**
 * The conditions of a practice attempt (Volume 12, prompt 3; docs/ATTEMPT_CONDITIONS.md): the page
 * shows exactly the labels the server derived, where it says them, and nothing the app can't see.
 */
const NOTE = "Only help shown in CodeCoach is recorded. Help from anywhere else isn't known, and accessibility settings such as dictation or captions are never counted as help.";
const conditions = (over: Partial<AttemptConditions> = {}): AttemptConditions => ({
  labels: ["No in-app help recorded"], help: [], recorded_from: "2026-11-14", note: NOTE, ...over,
});
const hinted = conditions({
  labels: ["Hint shown", "Solution revealed"],
  help: [
    { label: "Hint shown", detail: "Level 1 hint (nudge)", at: "2026-11-14T10:00:00Z" },
    { label: "Solution revealed", detail: "Level 4 hint (full explanation): the full explanation", at: "2026-11-14T10:05:00Z" },
  ],
});
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: "registered-nurse" } }))));

describe("What help was part of an attempt", () => {
  it("an attempt's page lists the help shown before it, with times", async () => {
    server.use(http.get(`${API}/api/v1/submissions/:id`, () => HttpResponse.json({ ...queuedSubmission, conditions: hinted })));
    renderApp("/history/submissions/sub-1", { signedIn: true });
    const card = (await screen.findByRole("heading", { name: "In-app help" })).closest(".card") as HTMLElement;
    expect(within(card).getByText(/^In-app help before this attempt:/).parentElement).toHaveTextContent("Hint shown, Solution revealed");
    expect(within(card).getByText(/Hint shown: Level 1 hint \(nudge\)/)).toBeInTheDocument();
    expect(within(card).getByText(/Solution revealed: Level 4 hint/)).toBeInTheDocument();
    expect(within(card).getByText(/never counted as help\. It doesn't change the score or the verdict\./)).toBeInTheDocument();
    for (const word of [/independent/i, /unassisted/i, /verified/i]) expect(card.textContent).not.toMatch(word);
  });

  it("an attempt from before recording began says not recorded, and since when it's recorded", async () => {
    server.use(http.get(`${API}/api/v1/submissions/:id`, () => HttpResponse.json({ ...queuedSubmission, conditions: conditions({ labels: ["Not recorded"] }) })));
    renderApp("/history/submissions/sub-1", { signedIn: true });
    const line = (await screen.findByText(/^In-app help before this attempt:/)).parentElement!;
    expect(line).toHaveTextContent(/Not recorded \(help is recorded from [^)]*Nov 14, 2026\)/);
    expect(line.textContent).not.toMatch(/none/i);
  });

  it("History shows each attempt's labels, asked for once for the rows on screen", async () => {
    const asked: { submission_ids?: string[]; answer_ids?: string[] }[] = [];
    server.use(
      http.get(`${API}/api/v1/me/activity`, () => HttpResponse.json({ items: activityItems, total: activityItems.length, page: 1, page_size: 20 })),
      http.post(`${API}/api/v1/me/attempt-conditions`, async ({ request }) => {
        asked.push((await request.json()) as { submission_ids?: string[]; answer_ids?: string[] });
        return HttpResponse.json({ submissions: { "sub-1": hinted }, answers: { "a-1": conditions() } });
      }),
    );
    renderApp("/history", { signedIn: true });
    expect(await screen.findByText(/In-app help: Hint shown, Solution revealed/)).toBeInTheDocument();
    expect(screen.getByText(/In-app help: No in-app help recorded/)).toBeInTheDocument();
    expect(asked).toEqual([{ submission_ids: ["sub-1"], answer_ids: ["a-1"] }]);
    // The mock interview row has no attempt conditions.
    const round = screen.getByText("Registered Nurse question round").closest("a")!;
    expect(round.textContent).not.toMatch(/In-app help/);
  });

  it("a written answer shows its conditions in the past answers and beside its feedback", async () => {
    asNurse();
    const past: InterviewAnswer[] = [{ ...nurseAnswer, id: "a-2", created_at: "2026-11-14T11:00:00Z", conditions: conditions() },
      { ...nurseAnswer, id: "a-1", created_at: "2026-11-14T10:00:00Z", conditions: conditions({ labels: ["Hint shown"], help: [{ label: "Hint shown", detail: "Lesson “SBAR for handoffs and escalation” read", at: "2026-11-14T09:00:00Z" }] }) }];
    server.use(http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json(past)));
    renderApp("/careers/registered-nurse/questions/m-pressure-0?answer=a-1", { signedIn: true });
    const list = (await screen.findByRole("heading", { name: "Your past answers" })).closest(".card") as HTMLElement;
    await waitFor(() => expect(within(list).getAllByRole("button")).toHaveLength(2));
    const [newer, older] = within(list).getAllByRole("button");
    expect(newer).toHaveTextContent("No in-app help recorded");
    expect(older).toHaveTextContent("Hint shown");
    expect(await screen.findByText(/Hint shown: Lesson “SBAR for handoffs and escalation” read/)).toBeInTheDocument();
  });

  it("dictation and captions on: nothing about them is sent with an answer, and it shows no help", async () => {
    asNurse();
    localStorage.setItem("codecoach.voice", JSON.stringify({ captions: true, readAloud: true }));
    let body: Record<string, unknown> | null = null;
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ ...nurseAnswer, conditions: conditions() }, { status: 201 });
    }));
    const { user } = renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Last winter, on nights, a patient's oxygen dropped and I escalated.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await screen.findByRole("region", { name: "Feedback" });
    expect(Object.keys(body ?? {}).sort()).toEqual(["answer", "client_request_id"].filter((k) => k in (body ?? {})).sort());
    expect(JSON.stringify(body)).not.toMatch(/caption|dictat|voice|read_?aloud|contrast|motion|text_?size/i);
    expect(await screen.findByText(/^In-app help before this attempt:/)).toBeInTheDocument();
    expect(screen.getByText(/^In-app help before this attempt:/).parentElement).toHaveTextContent("No in-app help recorded");
  });
});
