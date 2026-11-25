/**
 * Undo for every removal from the review queue (Volume 18, prompt 1; docs/DISPUTES.md, "Removing a
 * point"): the queue's own Remove, on a scheduled question or one there only for disputed feedback,
 * says what it took out and that its answers, scores and disputes stay, moves the keyboard's place to
 * Undo (the Remove button has gone with its row), and Undo puts it back as it was. A refused Undo
 * (saved again meanwhile) says why and leaves the question where it is. Synthetic data only.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ReviewQueueItem } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = new Date().toISOString();

const item = (id: string, title: string): ReviewQueueItem => ({
  id, track: "registered-nurse", career_title: "Registered Nurse", question_id: `q-${id}`, title,
  href: `/careers/registered-nurse/questions/q-${id}`, due_at: now, due: false, interval_days: 3, last_score: 62, reviews: 1,
  snoozed: false, criterion: null, points: [], recounted: null, why: "Due Nov 18.",
});
const empty = { due: [], upcoming: [], disputed: [], ladder_days: [1, 3, 7, 14, 30], note: "" };

function serveQueue(start: { upcoming?: ReviewQueueItem[]; disputed?: ReviewQueueItem[] }, restoreReply?: () => Response) {
  let current = { ...empty, ...start };
  const calls: string[] = [];
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/me/reviews`, () => HttpResponse.json(current)),
    http.delete(`${API}/api/v1/me/reviews/:id`, ({ params }) => {
      calls.push(`remove ${String(params.id)}`);
      current = { ...current, upcoming: current.upcoming.filter((i) => i.id !== params.id), disputed: current.disputed.filter((i) => i.id !== params.id) };
      return HttpResponse.json(current);
    }),
    http.post(`${API}/api/v1/me/reviews/:id/restore`, ({ params }) => {
      calls.push(`restore ${String(params.id)}`);
      if (restoreReply) return restoreReply();
      current = { ...empty, ...start };
      return HttpResponse.json(current);
    }),
  );
  return calls;
}

describe("Undo after the review queue's own Remove", () => {
  it("a scheduled question: says what it took out, focuses Undo, and Undo puts it back", async () => {
    const calls = serveQueue({ upcoming: [item("rv-1", "A hard shift"), item("rv-2", "Calming a family")] });
    const { user } = renderApp("/reviews", { signedIn: true });
    const row = await screen.findByRole("listitem", { name: "A hard shift" });
    await user.click(within(row).getByRole("button", { name: "Remove" }));
    const undo = await screen.findByRole("status");
    expect(undo).toHaveTextContent("Took “A hard shift” out of your review queue. Its answers, scores and any disputes stay.");
    expect(screen.queryByRole("listitem", { name: "A hard shift" })).toBeNull();
    expect(screen.getByRole("listitem", { name: "Calming a family" })).toBeInTheDocument();
    await waitFor(() => expect(within(undo).getByRole("button", { name: "Undo" })).toHaveFocus());
    await user.click(within(undo).getByRole("button", { name: "Undo" }));
    expect(await screen.findByRole("listitem", { name: "A hard shift" })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/^Took “A hard shift”/)).toBeNull());
    expect(calls).toEqual(["remove rv-1", "restore rv-1"]);
  });

  it("a question there only for disputed feedback has Undo too", async () => {
    const disputed = { ...item("rv-3", "Escalating a concern"), why: "Saved only from feedback you disputed." };
    const calls = serveQueue({ disputed: [disputed] });
    const { user } = renderApp("/reviews", { signedIn: true });
    const row = await screen.findByRole("listitem", { name: "Escalating a concern" });
    await user.click(within(row).getByRole("button", { name: "Remove" }));
    const undo = await screen.findByRole("status");
    expect(undo).toHaveTextContent("Took “Escalating a concern” out of your review queue.");
    await user.click(within(undo).getByRole("button", { name: "Undo" }));
    expect(await screen.findByRole("listitem", { name: "Escalating a concern" })).toBeInTheDocument();
    expect(calls).toEqual(["remove rv-3", "restore rv-3"]);
  });

  it("a refused Undo says why, and the question stays out", async () => {
    serveQueue({ upcoming: [item("rv-1", "A hard shift")] }, () => HttpResponse.json(
      { error: { code: "already_in_queue", message: "It's back in your review queue already: it was saved again." } }, { status: 409 }));
    const { user } = renderApp("/reviews", { signedIn: true });
    await user.click(within(await screen.findByRole("listitem", { name: "A hard shift" })).getByRole("button", { name: "Remove" }));
    const undo = await screen.findByRole("status");
    await user.click(within(undo).getByRole("button", { name: "Undo" }));
    expect(await screen.findByText("It's back in your review queue already: it was saved again.")).toBeInTheDocument();
    expect(screen.queryByRole("listitem", { name: "A hard shift" })).toBeNull();
  });
});
