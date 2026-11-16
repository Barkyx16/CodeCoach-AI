/**
 * A question saved for review for several points (Volume 16, prompt 5; docs/DISPUTES.md, "The review
 * queue"): the queue lists every point, one point reads as before, and with several each can be taken
 * off, keeping the question. Synthetic data only.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ReviewQueueItem } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = new Date().toISOString();
const A = "Explains what you personally did";
const B = "Backs it up with a concrete example";

const item = (points: string[]): ReviewQueueItem => ({
  id: "rv-1", track: "registered-nurse", career_title: "Registered Nurse", question_id: "e-time-0", title: "A hard shift",
  href: "/careers/registered-nurse/questions/e-time-0", due_at: now, due: false, interval_days: 3, last_score: 90, reviews: 1,
  snoozed: false, criterion: points[0] ?? null, points, recounted: null, why: "Due Nov 18.",
});
const queue = (points: string[]) => ({ due: [], upcoming: [item(points)], disputed: [], ladder_days: [1, 3, 7, 14, 30], note: "" });

describe("A question saved for several points", () => {
  it("lists every point and takes one off, keeping the question", async () => {
    const removed: string[] = [];
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/me/reviews`, () => HttpResponse.json(queue([A, B]))),
      http.delete(`${API}/api/v1/me/reviews/rv-1/points`, ({ request }) => {
        removed.push(new URL(request.url).searchParams.get("point") ?? "");
        return HttpResponse.json(queue([A]));
      }),
    );
    const { user } = renderApp("/reviews", { signedIn: true });
    const row = await screen.findByRole("listitem", { name: "A hard shift" });
    expect(within(row).getByText("Saved for 2 points:")).toBeInTheDocument();
    const list = within(row).getByRole("list", { name: "Points “A hard shift” is saved for" });
    expect(within(list).getAllByRole("listitem").map((li) => li.textContent?.split("”")[0])).toEqual([`“${A}`, `“${B}`]);
    await user.click(within(row).getByRole("button", { name: `Remove the point “${B}”` }));
    await waitFor(() => expect(removed).toEqual([B]));
    expect(await within(await screen.findByRole("listitem", { name: "A hard shift" })).findByText(`Saved for “${A}”.`)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove the point/ })).toBeNull(); // the last point stays
  });

  it("an item with one point, or from before this, reads as it did", async () => {
    const before = { ...item([]), criterion: A, points: undefined } as unknown as ReviewQueueItem;
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/me/reviews`, () => HttpResponse.json({ ...queue([]), upcoming: [before] })),
    );
    renderApp("/reviews", { signedIn: true });
    const row = await screen.findByRole("listitem", { name: "A hard shift" });
    expect(within(row).getByText(`Saved for “${A}”.`)).toBeInTheDocument();
    expect(within(row).queryByRole("button", { name: /Remove the point/ })).toBeNull();
  });
});
