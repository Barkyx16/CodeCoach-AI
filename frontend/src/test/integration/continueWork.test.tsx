/**
 * "Continue your work" (Volume 11, prompt 1; docs/CONTINUE.md): saved records with the time each
 * really keeps and the right destination, a finished interview opening its results, drafts kept in
 * this browser labelled as such, an earlier action checked (read-only) instead of sent again, one
 * failing source leaving the rest, hiding that sticks, nothing started by loading, deleted records
 * dropping out, and another account never inheriting a title.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { vi } from "vitest";

import type { RecentItem } from "@/api/types";
import { CONTINUE_HIDDEN_KEY } from "@/features/dashboard/ContinueCard";
import { keyForIntent, listIntents } from "@/lib/pendingIntents";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const ME = baseUser.id;
const hour = (n: number) => new Date(Date.now() - n * 3_600_000).toISOString();
const items: RecentItem[] = [
  { type: "note", id: "n-1", title: "Sepsis signs", at: hour(1), at_meaning: "saved", state: null, detail: null, parent_id: null },
  { type: "kit", id: "ev-1", parent_id: "app-1", title: "Interview-day kit: Panel interview (Northfield)", detail: "on 2026-12-15", at: hour(2), at_meaning: "saved", state: null },
  { type: "interview", id: "iv-done", title: "Registered Nurse question round", state: "ended_early", at: hour(3), at_meaning: "finished", detail: null, parent_id: null },
  { type: "story", id: "s-1", title: "Night shift", at: hour(4), at_meaning: "saved", state: null, detail: null, parent_id: null },
];

let requests: string[] = [];
function serve(recent: unknown = { items, unavailable: [] }, status = 200) {
  requests = [];
  server.events.removeAllListeners();
  server.events.on("request:start", ({ request }) => { requests.push(`${request.method} ${new URL(request.url).pathname}`); });
  server.use(http.get(`${API}/api/v1/me/recent-work`, () => HttpResponse.json(recent as object, { status })));
}
afterEach(() => { server.events.removeAllListeners(); vi.restoreAllMocks(); });

const section = () => screen.findByRole("region", { name: "Continue your work" });

describe("Continue your work", () => {
  it("lists saved records with honest times and the right destinations, and starts nothing by loading", async () => {
    serve();
    window.localStorage.setItem(`codecoach.answer.${ME}.software-engineer.q-1`, "A draft answer");
    renderApp("/dashboard", { signedIn: true });
    const saved = await within(await section()).findByRole("group", { name: "Saved to your account" });
    const link = async (name: RegExp) => within(saved).findByRole("link", { name });
    expect(await link(/Sepsis signs/)).toHaveAttribute("href", "/notes/n-1");
    expect(await link(/Sepsis signs/)).toHaveTextContent(/Note · saved .*hour.* ago · Open/);
    expect(await link(/Interview-day kit/)).toHaveAttribute("href", "/applications/app-1/events/ev-1/kit");
    expect(await link(/Interview-day kit/)).toHaveTextContent("on 2026-12-15");
    const done = await link(/question round/);
    expect(done).toHaveAttribute("href", "/interviews/iv-done");
    expect(done).toHaveTextContent(/Interview · ended early · finished .* ago · See results/); // a result, not a session
    expect(done).not.toHaveTextContent("Resume");
    expect(await link(/Night shift/)).toHaveAttribute("href", "/stories/s-1");
    expect(saved).not.toHaveTextContent(/opened/i); // the app doesn't record that
    const device = within(await section()).getByRole("group", { name: "Only in this browser" });
    expect(device).toHaveTextContent("Not on your account yet, and not on your other devices.");
    expect(within(device).getByRole("link", { name: /Finish your answer/ })).toBeInTheDocument();
    // Loading only reads: no submission, answer, interview or AI request is sent.
    expect(requests.filter((r) => !r.startsWith("GET") && r !== "POST /api/v1/auth/refresh")).toEqual([]);
  });

  it("takes you back to a scenario run in progress and to a test-design run waiting or finished (Volume 19, prompt 6)", async () => {
    serve({ items: [
      { type: "scenario_run", id: "sc-1", title: "Two patients, one nurse", at: hour(1), at_meaning: "started", state: null, detail: null, parent_id: null },
      { type: "test_design_run", id: "td-1", parent_id: "tests-count-in-range", title: "Test design: Count in Range", detail: "Waiting for the judge · version 1", at: hour(2), at_meaning: "saved", state: null },
      { type: "test_design_run", id: "td-2", parent_id: "tests-count-in-range", title: "Test design: Count in Range", detail: "Told apart 2 of 4 faulty versions · version 1", at: hour(3), at_meaning: "finished", state: null },
    ], unavailable: [] });
    renderApp("/dashboard", { signedIn: true });
    const saved = await within(await section()).findByRole("group", { name: "Saved to your account" });
    const scenario = await within(saved).findByRole("link", { name: /Two patients, one nurse/ });
    expect(scenario).toHaveAttribute("href", "/scenarios/attempts/sc-1");
    expect(scenario).toHaveTextContent(/Scenario run · started .*hour.* ago · Resume$/);
    const [waiting, judged] = within(saved).getAllByRole("link", { name: /Test design: Count in Range/ });
    expect(waiting).toHaveAttribute("href", "/test-design/tests-count-in-range?attempt=td-1");
    expect(waiting).toHaveTextContent(/Test design run · Waiting for the judge · version 1 · saved .* ago · Open$/);
    expect(judged).toHaveAttribute("href", "/test-design/tests-count-in-range?attempt=td-2");
    expect(judged).toHaveTextContent(/Test design run · Told apart 2 of 4 faulty versions · version 1 · finished .* ago · Open$/);
    expect(requests.filter((r) => !r.startsWith("GET") && r !== "POST /api/v1/auth/refresh")).toEqual([]); // nothing resumed by loading
  });

  it("lists a debugging exercise not fixed yet, a run at its last step, once each (Volume 20, prompt 6)", async () => {
    const listed = [
      { type: "debug_exercise", id: "debug-coldest-day", title: "Fix: Coldest Reading", detail: "Not fixed yet: 3 of 7 tests pass", at: hour(1), at_meaning: "tried", state: null, parent_id: null },
      { type: "scenario_run", id: "sc-1", title: "Two patients, one nurse", at: hour(2), at_meaning: "last_step", state: null, detail: null, parent_id: null },
      { type: "scenario_run", id: "sc-2", title: "Checkout is down", at: hour(3), at_meaning: "started", state: null, detail: null, parent_id: null },
      // A kind a newer server might add: left out here, never opened blindly.
      { type: "something_later", id: "x-1", title: "From a later version", at: hour(4), at_meaning: "saved", state: null, detail: null, parent_id: null },
    ];
    serve({ items: listed, unavailable: [] });
    let asked = "";
    server.use(
      http.get(`${API}/api/v1/me/recent-work`, ({ request }) => {
        asked = new URL(request.url).searchParams.get("shows") ?? "";
        return HttpResponse.json({ items: listed, unavailable: [] });
      }),
      // The same exercise as the last unsolved problem: listed once, as tried.
      http.get(`${API}/api/v1/me/resume`, () => HttpResponse.json({
        interview: null, last_question: null,
        unfinished_problem: { slug: "debug-coldest-day", title: "Fix: Coldest Reading", last_status: "failed", at: hour(1) },
      })),
    );
    renderApp("/dashboard", { signedIn: true });
    const saved = await within(await section()).findByRole("group", { name: "Saved to your account" });
    const exercise = await within(saved).findByRole("link", { name: /Fix: Coldest Reading/ });
    expect(exercise).toHaveAttribute("href", "/problems/debug-coldest-day");
    expect(exercise).toHaveTextContent(/^Fix: Coldest ReadingDebugging exercise · Not fixed yet: 3 of 7 tests pass · tried .*hour.* ago · Resume$/);
    expect(asked.split(",").sort()).toEqual(["debug_exercise", "last_step"]); // what this page can show
    await waitFor(() => expect(requests).toContain("GET /api/v1/me/resume"));
    expect(within(saved).getAllByRole("link", { name: /Fix: Coldest Reading/ })).toHaveLength(1);
    expect(saved).not.toHaveTextContent("Coding problem");
    expect(within(saved).getByRole("link", { name: /Two patients, one nurse/ })).toHaveTextContent(/Scenario run · last step .*hours? ago · Resume$/);
    expect(within(saved).getByRole("link", { name: /Checkout is down/ })).toHaveTextContent(/Scenario run · started .*hours? ago · Resume$/);
    expect(saved).not.toHaveTextContent("From a later version");
    expect(requests.filter((r) => !r.startsWith("GET") && r !== "POST /api/v1/auth/refresh")).toEqual([]); // nothing started by loading
  });

  it("checks an earlier action without sending it again, and shows where it went", async () => {
    serve();
    const story = keyForIntent(ME, "story", "new", "print-story").key;
    keyForIntent(ME, "submission", "two-sum", "print-sub");
    const sub = listIntents(ME).find((i) => i.kind === "submission")!.key;
    server.use(http.get(`${API}/api/v1/me/requests/:key`, ({ params }) => (params.key === story
      ? HttpResponse.json({ kind: "story", state: "done", id: "s-9", created_at: hour(1), problem_slug: null, hint_level: null })
      : HttpResponse.json({ error: { code: "not_found", message: "No request with that key.", request_id: "r", details: null } }, { status: 404 }))));
    const { user } = renderApp("/dashboard", { signedIn: true });
    const waiting = within(await section()).getByRole("group", { name: "Waiting for a reply" });
    expect(waiting).toHaveTextContent("nothing is sent again");
    const rows = within(waiting).getAllByRole("listitem");
    const storyRow = rows.find((r) => r.textContent?.includes("Story save"))!;
    const subRow = rows.find((r) => r.textContent?.includes("Code submission"))!;
    await user.click(within(storyRow).getByRole("button", { name: "Check result" }));
    expect(await within(storyRow).findByText(/It arrived\./)).toBeInTheDocument();
    expect(within(storyRow).getByRole("link", { name: "Open the story" })).toHaveAttribute("href", "/stories/s-9");
    await user.click(within(subRow).getByRole("button", { name: "Check result" }));
    expect(await within(subRow).findByText(/It never arrived, so nothing was made/)).toBeInTheDocument();
    expect(requests.filter((r) => r.startsWith("GET /api/v1/me/requests/")).sort()).toEqual([`GET /api/v1/me/requests/${story}`, `GET /api/v1/me/requests/${sub}`].sort());
    expect(requests.some((r) => r.startsWith("POST /api/v1/submissions") || r.startsWith("POST /api/v1/me/stories"))).toBe(false);
    expect(listIntents(ME)).toEqual([]); // both answered: their records are done with
  });

  it("keeps the rest when one source fails, and names a kind that couldn't be read", async () => {
    serve({ error: { code: "internal", message: "boom", request_id: "r", details: null } }, 500);
    server.use(http.get(`${API}/api/v1/me/resume`, () => HttpResponse.json({
      interview: { id: "iv-live", kind: "questions", title: "Live round", deadline_at: new Date(Date.now() + 600_000).toISOString(), seconds_remaining: 600 },
      unfinished_problem: null, last_question: null,
    })));
    const first = renderApp("/dashboard", { signedIn: true, queries: { retry: false } });
    const card = await section();
    expect(await within(card).findByText(/couldn't be loaded just now\. The rest of this section still works/)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: /Resume interview/ })).toHaveAttribute("href", "/interviews/iv-live");
    expect(within(card).getByRole("button", { name: "Try again" })).toBeInTheDocument();
    first.unmount();

    serve({ items: items.slice(1), unavailable: ["notes"] });
    renderApp("/dashboard", { signedIn: true });
    const saved = await within(await section()).findByRole("group", { name: "Saved to your account" });
    expect(await within(saved).findByText("Your notes couldn't be loaded just now; everything else is listed.")).toBeInTheDocument();
    expect(within(saved).getByRole("link", { name: /Night shift/ })).toBeInTheDocument();
  });

  it("can be hidden, stays hidden after a reload, and comes back when asked", async () => {
    serve();
    const first = renderApp("/dashboard", { signedIn: true });
    await first.user.click(within(await section()).getByRole("button", { name: "Hide" }));
    expect(screen.queryByRole("region", { name: "Continue your work" })).not.toBeInTheDocument();
    expect(window.localStorage.getItem(CONTINUE_HIDDEN_KEY)).toBe("1");
    first.unmount();
    serve();
    const second = renderApp("/dashboard", { signedIn: true });
    const show = await screen.findByRole("button", { name: "Show it" });
    await screen.findByRole("heading", { level: 1 }); // the dashboard has loaded around it
    await new Promise((r) => setTimeout(r, 50));
    expect(requests.filter((r) => r.includes("recent-work"))).toEqual([]); // hidden: nothing fetched for it
    await second.user.click(show);
    expect(await section()).toBeInTheDocument();
    await waitFor(() => expect(requests.filter((r) => r.includes("recent-work"))).toHaveLength(1));
  });

  it("drops a record deleted elsewhere the next time the dashboard shows", async () => {
    let current = items;
    serve();
    server.use(http.get(`${API}/api/v1/me/recent-work`, () => HttpResponse.json({ items: current, unavailable: [] })));
    const { router } = renderApp("/dashboard", { signedIn: true });
    expect(await within(await section()).findByRole("link", { name: /Sepsis signs/ })).toBeInTheDocument();
    current = items.filter((i) => i.id !== "n-1"); // deleted on another device
    await router.navigate("/settings");
    expect(await screen.findByRole("heading", { name: "Settings", level: 1 }, { timeout: 3000 })).toBeInTheDocument(); // the dashboard is gone
    await router.navigate("/dashboard");
    await waitFor(async () => expect(within(await section()).queryByRole("link", { name: /Sepsis signs/ })).not.toBeInTheDocument());
    expect(within(await section()).getByRole("link", { name: /Night shift/ })).toBeInTheDocument();
  });

  it("another account signing in sees none of the first account's titles", async () => {
    const bea = { ...baseUser, id: "u-bea", email: "bea@example.com", display_name: "Bea" };
    let who = "ada";
    serve();
    server.use(
      http.get(`${API}/api/v1/me/recent-work`, () => HttpResponse.json(who === "ada"
        ? { items, unavailable: [] }
        : { items: [{ type: "note", id: "n-b", title: "Bea's own note", at: hour(1), at_meaning: "saved", state: null, detail: null, parent_id: null }], unavailable: [] })),
      http.post(`${API}/api/v1/auth/login`, () => { who = "bea"; return HttpResponse.json(tokenResponse({ user: bea })); }),
    );
    const { user, router } = renderApp("/dashboard", { signedIn: true });
    expect(await within(await section()).findByRole("link", { name: /Sepsis signs/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(router.state.location.pathname).not.toBe("/dashboard"));
    await router.navigate("/login");
    await user.type(await screen.findByLabelText("Email"), bea.email);
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.state.location.pathname).not.toBe("/login"));
    await router.navigate("/dashboard");
    expect(await within(await section()).findByRole("link", { name: /Bea's own note/ })).toBeInTheDocument();
    expect(screen.queryByText("Sepsis signs")).not.toBeInTheDocument();
    expect(screen.queryByText("Night shift")).not.toBeInTheDocument();
  });
});
