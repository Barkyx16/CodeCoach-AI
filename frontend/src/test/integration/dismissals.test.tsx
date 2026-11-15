/**
 * Suggestions dismissed with "Not now", kept with the account (Volume 15, prompt 2;
 * docs/FOLLOW_UPS.md, "Not now"): Settings lists them in plain words and offers each again; a
 * dismissal kept only in this browser before is carried over once, then the browser copy goes; the
 * plan's change notice is dismissed for the account.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Dismissed } from "@/api/types";
import { carryOverLocalDismissals, resetCarryOverForTests } from "@/features/dismissals/dismissals";

import { renderApp } from "../render";
import { API, server } from "../server";

const QUESTION: Dismissed = {
  key: "question-follow-up:registered-nurse/e-inform-0>e-inform-2", kind: "question_follow_up",
  label: "A related question: Keeping patients' families informed (after “Keeping patients informed”)", note: null,
  offered_on: "/careers/registered-nurse/questions/e-inform-0", dismissed_at: "2026-11-12T09:00:00Z",
};
const PROBLEM: Dismissed = {
  key: "problem-follow-up:two-sum>two-sum-sorted", kind: "problem_follow_up",
  label: "A related problem: Two Sum in a Sorted Array (after Two Sum)", note: "You've tried this problem since, so it won't be offered again.",
  offered_on: "/problems/two-sum", dismissed_at: "2026-11-13T09:00:00Z",
};

beforeEach(() => {
  localStorage.clear();
  resetCarryOverForTests();
});

describe("Suggestions you dismissed", () => {
  it("lists them in plain words, says what offering one again will do, and offers it again", async () => {
    let items = [PROBLEM, QUESTION];
    const removed: string[] = [];
    server.use(
      http.get(`${API}/api/v1/me/dismissals`, () => HttpResponse.json({ items })),
      http.delete(`${API}/api/v1/me/dismissals`, ({ request }) => {
        const key = new URL(request.url).searchParams.get("key")!;
        removed.push(key);
        items = items.filter((i) => i.key !== key);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user } = renderApp("/settings", { signedIn: true });
    const list = await screen.findByRole("list", { name: "Suggestions you dismissed" }, { timeout: 4000 });
    const rows = within(list).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("A related problem: Two Sum in a Sorted Array (after Two Sum)");
    expect(rows[0]).toHaveTextContent("You've tried this problem since, so it won't be offered again.");
    expect(rows[1]).toHaveTextContent("A related question: Keeping patients' families informed");
    await user.click(within(rows[1]!).getByRole("button", { name: /^Offer it again: A related question/ }));
    await waitFor(() => expect(within(list).getAllByRole("listitem")).toHaveLength(1));
    expect(removed).toEqual([QUESTION.key]);
  });

  it("says so when nothing is dismissed", async () => {
    renderApp("/settings", { signedIn: true });
    expect(await screen.findByText("Nothing dismissed.", undefined, { timeout: 4000 })).toBeInTheDocument();
  });
});

describe("Carrying over what this browser kept before", () => {
  function recording() {
    const sent: string[] = [];
    server.use(
      http.post(`${API}/api/v1/me/dismissals`, async ({ request }) => {
        const body = (await request.json()) as { items: { key: string }[] };
        const key = body.items[0]!.key;
        if (key.includes("gone")) return HttpResponse.json({ error: { code: "invalid_dismissal", message: "x", request_id: "r", details: null } }, { status: 400 });
        sent.push(key);
        return HttpResponse.json({ items: [] });
      }),
    );
    return sent;
  }

  it("sends each once, then clears the browser copy, so a second load sends nothing", async () => {
    const sent = recording();
    localStorage.setItem("codecoach.followups.dismissed.v1.u-1", JSON.stringify(["registered-nurse/e-inform-0>e-inform-2", "registered-nurse/x>gone"]));
    localStorage.setItem("codecoach.plan.seen.registered-nurse", "3");
    localStorage.setItem("codecoach.followups.dismissed.v1.someone-else", JSON.stringify(["registered-nurse/a>b"]));
    expect(await carryOverLocalDismissals("u-1")).toBe(2);
    expect(sent.sort()).toEqual(["plan-change:registered-nurse@3", "question-follow-up:registered-nurse/e-inform-0>e-inform-2"]);
    // Cleared, the refused one too (it can never be carried); another account's left alone.
    expect(localStorage.getItem("codecoach.followups.dismissed.v1.u-1")).toBeNull();
    expect(localStorage.getItem("codecoach.plan.seen.registered-nurse")).toBeNull();
    expect(localStorage.getItem("codecoach.followups.dismissed.v1.someone-else")).not.toBeNull();
    expect(await carryOverLocalDismissals("u-1")).toBe(0);
    expect(sent).toHaveLength(2);
  });

  it("keeps the browser copy when the connection is lost, for next time", async () => {
    server.use(http.post(`${API}/api/v1/me/dismissals`, () => HttpResponse.error()));
    localStorage.setItem("codecoach.followups.dismissed.v1.u-1", JSON.stringify(["registered-nurse/e-inform-0>e-inform-2"]));
    expect(await carryOverLocalDismissals("u-1")).toBe(0);
    expect(localStorage.getItem("codecoach.followups.dismissed.v1.u-1")).not.toBeNull();
  });

  it("runs once when a signed-in page loads", async () => {
    const sent = recording();
    localStorage.setItem("codecoach.plan.seen.registered-nurse", "2");
    renderApp("/settings", { signedIn: true });
    await waitFor(() => expect(sent).toEqual(["plan-change:registered-nurse@2"]));
  });
});
