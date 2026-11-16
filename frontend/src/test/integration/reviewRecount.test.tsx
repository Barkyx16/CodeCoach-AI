/**
 * Volume 15, prompt 9 (docs/DISPUTES.md, "The review queue"): a point to work on can be saved for
 * review for that point, which the request says, and the queue shows what each item was saved for
 * and, when a dispute recounted its ladder, what changed. Synthetic data only.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Interview, InterviewReview } from "@/api/types";

import { nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = new Date().toISOString();
const POINT = "Explains what you personally did";

const interview: Interview = {
  id: "iv-r", kind: "questions", status: "completed", phase: null, phase_index: 5, phase_guide: null, problem: null,
  track: "registered-nurse", career_title: "Registered Nurse", questions: [], round_summary: null,
  duration_seconds: 900, started_at: now, deadline_at: now, ended_at: now, seconds_remaining: 0,
  candidate_turns_remaining: 30, provider: "built-in (offline)", turns: [], final_code: null, evaluation: null,
};

const review = (inQueue = false): InterviewReview => ({
  id: "iv-r", kind: "questions", track: "registered-nurse", career_title: "Registered Nurse", problem: null,
  status: "completed", status_label: "Completed", completed: true, started_at: now, ended_at: now,
  elapsed_seconds: 600, time_limit_seconds: 900, notices: [],
  items: [
    { key: "q1", index: 1, title: "A hard shift", prompt: "Tell me about a hard shift.", kind: "behavioral", role: "question",
      status: "answered", asked_at: now, answer_text: "We handled it as a team.", answered_at: now, source: "typed",
      transcription_note: null, engagement: null, feedback: { ...nurseAnswer, id: "a-1", score: 41 }, dimensions: [],
      retries: 0, in_review_queue: inQueue, question_id: "e-time-0" },
  ],
  overall: [],
  improvements: [{
    key: `point:${POINT}`, title: POINT, why: "Say “I” for your own actions. Missing in 1 of 1 answers.",
    evidence: [], practice: { label: "Retry “A hard shift”", retry_index: 1, href: null },
  }],
  evaluation_available: true, evaluator: "built-in (offline)", disclaimer: "", final_code: null,
});

function serve(r: InterviewReview) {
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/interviews/iv-r`, () => HttpResponse.json(interview)),
    http.get(`${API}/api/v1/interviews/iv-r/review`, () => HttpResponse.json(r)),
  );
}

describe("Saving a point for review (Volume 15, prompt 9)", () => {
  it("saves the question its retry targets, for that point, and says what a dispute of it does", async () => {
    let sent: unknown = null;
    serve(review());
    server.use(http.post(`${API}/api/v1/me/reviews`, async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({ due: [], upcoming: [], disputed: [], ladder_days: [1, 3, 7, 14, 30], note: "" });
    }));
    const { user } = renderApp("/interviews/iv-r", { signedIn: true });
    const list = (await screen.findByRole("heading", { name: "Work on next" })).closest("section, div")!;
    await user.click(within(list as HTMLElement).getByRole("button", { name: "Save this point for review" }));
    await waitFor(() => expect(sent).toEqual({ track: "registered-nurse", question_id: "e-time-0", session_id: "iv-r", criterion: POINT }));
    expect(await screen.findByText(`Saved for review, for “${POINT}”: if you dispute that point, it's held back.`)).toBeInTheDocument();
  });

  it("when the question is already in the queue, offers to add this point to it and says what changed (Volume 16, prompt 5)", async () => {
    serve(review(true));
    server.use(http.post(`${API}/api/v1/me/reviews`, () => HttpResponse.json({
      due: [], upcoming: [], disputed: [], ladder_days: [1, 3, 7, 14, 30], note: "", saved: `Added “${POINT}” to the points it's saved for.`,
    })));
    const { user } = renderApp("/interviews/iv-r", { signedIn: true });
    expect(await screen.findByText("“A hard shift” is already in your review queue; this adds the point to it.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save this point for review" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Add this point to its review" }));
    expect(await screen.findByText(`Added “${POINT}” to the points it's saved for.`)).toBeInTheDocument();
  });
});

describe("Removing a point from the interview summary (Volume 17, prompt 8)", () => {
  const OTHER = "Backs it up with a concrete example";
  const saved = (points: string[]): InterviewReview => {
    const r = review(true);
    return { ...r, items: r.items.map((i) => ({ ...i, review_item_id: "rv-1", review_points: points })) };
  };
  const emptyQueue = { due: [], upcoming: [], disputed: [], ladder_days: [1, 3, 7, 14, 30], note: "" };

  it("with other points saved, takes only this one off", async () => {
    const removed: string[] = [];
    serve(saved([POINT, OTHER]));
    server.use(http.delete(`${API}/api/v1/me/reviews/rv-1/points`, ({ request }) => {
      removed.push(new URL(request.url).searchParams.get("point") ?? "");
      return HttpResponse.json(emptyQueue);
    }));
    const { user } = renderApp("/interviews/iv-r", { signedIn: true });
    expect(await screen.findByText(`Saved for review, for “${POINT}” (and 1 other point): if you dispute that point, it's held back.`)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: `Remove the point “${POINT}”` }));
    await waitFor(() => expect(removed).toEqual([POINT]));
    expect(screen.queryByText(/is the only point/)).toBeNull(); // nothing to confirm: the question stays
  });

  it("its only point: says what removing it does first, then Undo puts the question back", async () => {
    const calls: string[] = [];
    serve(saved([POINT]));
    server.use(
      http.delete(`${API}/api/v1/me/reviews/rv-1/points`, () => { calls.push("point"); return HttpResponse.json(emptyQueue); }),
      http.delete(`${API}/api/v1/me/reviews/rv-1`, () => { calls.push("remove"); return HttpResponse.json(emptyQueue); }),
      http.post(`${API}/api/v1/me/reviews/rv-1/restore`, () => { calls.push("restore"); return HttpResponse.json(emptyQueue); }),
    );
    const { user } = renderApp("/interviews/iv-r", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: `Remove the point “${POINT}”` }));
    const ask = screen.getByRole("group", { name: `Remove the point “${POINT}”` });
    expect(ask).toHaveTextContent(`“${POINT}” is the only point “A hard shift” is saved for, so removing it takes the question out of your review queue. Its answers, scores and any disputes stay.`);
    expect(calls).toEqual([]); // nothing sent before it's confirmed
    await user.click(within(ask).getByRole("button", { name: "Take it out of the queue" }));
    // The words say the answers, scores and disputes stay (Volume 18, prompt 1).
    const undone = (await screen.findByText("Took “A hard shift” out of your review queue. Its answers, scores and any disputes stay.")).closest("[role=status]") as HTMLElement;
    await user.click(within(undone).getByRole("button", { name: "Undo" }));
    await waitFor(() => expect(calls).toEqual(["remove", "restore"])); // the question, never "point"
    expect(await screen.findByRole("button", { name: `Remove the point “${POINT}”` })).toBeInTheDocument();
  });
});

describe("The queue says what an item was saved for and what a recount changed", () => {
  it("shows the point and the recount", async () => {
    const recounted = "Recounted: one earlier score was disputed (on “Explains what you personally did”, the point it was saved for), so it's due in 3 days, not 7.";
    const item = {
      id: "rv-1", track: "registered-nurse", career_title: "Registered Nurse", question_id: "e-time-0", title: "A hard shift",
      href: "/careers/registered-nurse/questions/e-time-0", due_at: now, due: false, interval_days: 3, last_score: 90, reviews: 1,
      snoozed: false, criterion: POINT, recounted,
      why: `Due Nov 18. Last answered Nov 15 scoring 90/100, so the gap grew to 3 days. ${recounted}`,
    };
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/me/reviews`, () => HttpResponse.json({ due: [], upcoming: [item], disputed: [], ladder_days: [1, 3, 7, 14, 30], note: "" })),
    );
    renderApp("/reviews", { signedIn: true });
    const row = await screen.findByRole("listitem", { name: "A hard shift" });
    expect(within(row).getByText(`Saved for “${POINT}”.`)).toBeInTheDocument();
    expect(row).toHaveTextContent(recounted);
  });
});
