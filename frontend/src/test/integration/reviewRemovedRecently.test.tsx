/**
 * Removed recently, on the review queue (Volume 19, prompt 2; docs/DISPUTES.md): questions taken out
 * of the queue in the last 30 days, listed after a reload (the page's own Undo lasts only while it's
 * open), collapsed by default, each with when it was removed (or that the date wasn't recorded) and
 * its points; Put back restores it as it was, says so, and keeps the keyboard's place; a refusal is
 * said in the server's words; nothing removed, no section. Synthetic data only.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { RemovedReviewItem, ReviewQueueItem } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const hoursAgo = (h: number) => new Date(Date.now() - h * 3600_000).toISOString();
const gone = (id: string, title: string, extra: Partial<RemovedReviewItem> = {}): RemovedReviewItem => ({
  id, track: "registered-nurse", career_title: "Registered Nurse", question_id: `q-${id}`, title,
  href: `/careers/registered-nurse/questions/q-${id}`, removed_at: hoursAgo(3), points: [], ...extra,
});
const queued = (r: RemovedReviewItem): ReviewQueueItem => ({
  id: r.id, track: r.track, career_title: r.career_title, question_id: r.question_id, title: r.title, href: r.href,
  due_at: new Date().toISOString(), due: false, interval_days: 3, last_score: 62, reviews: 1, snoozed: false,
  criterion: r.points[0] ?? null, points: r.points, recounted: null, why: "Due Nov 21.",
});
const empty = { due: [], upcoming: [] as ReviewQueueItem[], disputed: [], ladder_days: [1, 3, 7, 14, 30], note: "" };

function serve(start: RemovedReviewItem[], refuse?: () => Response) {
  let removed = [...start];
  let queue = { ...empty };
  const calls: string[] = [];
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/me/reviews`, () => HttpResponse.json(queue)),
    http.get(`${API}/api/v1/me/reviews/removed`, () => { calls.push("list"); return HttpResponse.json(removed); }),
    http.post(`${API}/api/v1/me/reviews/:id/restore`, ({ params }) => {
      calls.push(`restore ${String(params.id)}`);
      if (refuse) return refuse();
      const back = removed.find((r) => r.id === params.id)!;
      removed = removed.filter((r) => r.id !== params.id);
      queue = { ...queue, upcoming: [...queue.upcoming, queued(back)] };
      return HttpResponse.json(queue);
    }),
  );
  return calls;
}

describe("Removed recently on the review queue", () => {
  it("is collapsed, lists each removal with when and its points, and puts one back as it was", async () => {
    const calls = serve([
      gone("rv-1", "A hard shift", { points: ["Situation"] }),
      gone("rv-2", "Calming a family", { removed_at: null }),
    ]);
    const { user } = renderApp("/reviews", { signedIn: true });
    const toggle = await screen.findByRole("button", { name: "Removed recently (2)" }, { timeout: 3000 });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("list", { name: "Removed recently" })).toBeNull();
    await user.click(toggle);
    const list = screen.getByRole("list", { name: "Removed recently" });
    const first = within(list).getByRole("listitem", { name: "A hard shift" });
    expect(first).toHaveTextContent("Removed 3 hours ago · saved for “Situation”");
    expect(within(list).getByRole("listitem", { name: "Calming a family" })).toHaveTextContent("Removed earlier (date not recorded)");
    await user.click(within(first).getByRole("button", { name: "Put back: A hard shift" }));
    expect(await screen.findByText("“A hard shift” is back in your review queue, as it was.", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(calls).toContain("restore rv-1");
    await waitFor(() => expect(screen.getByRole("button", { name: "Removed recently (1)" })).toHaveFocus(), { timeout: 3000 });
    expect(await screen.findByRole("heading", { name: "Coming up (1)" }, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByRole("listitem", { name: "A hard shift" })).toHaveTextContent("Due Nov 21.");
  });

  it("a refused Put back says why and keeps the row", async () => {
    serve([gone("rv-1", "A hard shift")], () => HttpResponse.json(
      { error: { code: "already_in_queue", message: "It's back in your review queue already: it was saved again.", request_id: "r", details: null } }, { status: 409 }));
    const { user } = renderApp("/reviews", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Removed recently (1)" }, { timeout: 3000 }));
    const row = screen.getByRole("listitem", { name: "A hard shift" });
    await user.click(within(row).getByRole("button", { name: "Put back: A hard shift" }));
    expect(await within(row).findByText(/It's back in your review queue already: it was saved again\./, {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it("with nothing removed there is no section", async () => {
    const calls = serve([]);
    renderApp("/reviews", { signedIn: true });
    await screen.findByRole("heading", { name: "Review queue" }, { timeout: 3000 });
    await waitFor(() => expect(calls).toContain("list"), { timeout: 3000 });
    expect(screen.queryByRole("button", { name: /Removed recently/ })).toBeNull();
  });
});
