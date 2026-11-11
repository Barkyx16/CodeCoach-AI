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
