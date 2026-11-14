/**
 * Archive as a presentation lifecycle (Volume 11, prompt 4; docs/ARCHIVE.md): offer comparisons
 * get Active and Archived views with counts; archiving takes one out of the active list (focus moves
 * on, and the page says nothing was deleted), Restore brings it back; an archived comparison opens
 * with a banner and Restore; an application with an interview still to come asks before archiving
 * and says nothing is cancelled. Nothing but the archive flag is ever sent.
 */
import { act, screen, waitFor, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";

import type { Application, OfferComparison, OfferComparisonSummary } from "@/api/types";

import { renderApp } from "../render";
import { API, server } from "../server";

const now = () => new Date().toISOString();
const summary = (id: string, title: string, archived = false): OfferComparisonSummary => ({ id, title, offers: 2, archived, updated_at: now() });

let writes: string[] = [];
function trackWrites() {
  writes = [];
  server.events.removeAllListeners();
  server.events.on("request:start", ({ request }) => {
    if (request.method !== "GET" && !request.url.endsWith("/auth/refresh")) writes.push(`${request.method} ${new URL(request.url).pathname}`);
  });
}
afterEach(() => { server.events.removeAllListeners(); });

function comparisons(list: OfferComparisonSummary[], listDelay = 0) {
  const store = new Map(list.map((c) => [c.id, c]));
  server.use(
    http.get(`${API}/api/v1/me/offer-comparisons`, async ({ request }) => {
      if (listDelay) await delay(listDelay); // a list that takes a moment to come back
      const archived = new URL(request.url).searchParams.get("archived") === "true";
      return HttpResponse.json([...store.values()].filter((c) => c.archived === archived));
    }),
    http.post(`${API}/api/v1/me/offer-comparisons/:id/:action`, ({ params }) => {
      const c = store.get(String(params.id))!;
      const next = { ...c, archived: params.action === "archive" };
      store.set(c.id, next);
      return HttpResponse.json({ ...next, revision: 3, doc: { title: c.title, offers: [], factors: [], conversions: [], weights_on: false, show_in: null }, derived: {}, applications: {}, created_at: now() });
    }),
  );
  return store;
}

describe("Offer comparisons: active and archived", () => {
  it("archives from the active list, keeps focus, says nothing was deleted, and restores from Archived", async () => {
    comparisons([summary("c1", "Spring offers"), summary("c2", "Two hospitals"), summary("c3", "Last year's", true)], 150);
    trackWrites();
    const { user, router } = renderApp("/offers/compare", { signedIn: true });
    expect(await screen.findByRole("button", { name: "Active (2)" })).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByRole("button", { name: "Archived (1)" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Archive: Spring offers" }));
    expect(await screen.findByText(/"Spring offers" archived\. It's under Archived; nothing was deleted\./)).toBeInTheDocument();
    // When it's said, the counts already agree with it.
    expect(screen.getByRole("button", { name: "Archived (2)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Active (1)" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Spring offers" })).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Archive: Two hospitals" })).toHaveFocus()); // the next one
    expect(await screen.findByRole("button", { name: "Archived (2)" })).toBeInTheDocument();
    expect(writes).toEqual(["POST /api/v1/me/offer-comparisons/c1/archive"]); // only the flag

    await user.click(screen.getByRole("button", { name: "Show archived" }));
    expect(router.state.location.search).toBe("?archived=1");
    expect(await screen.findByRole("heading", { name: "Archived comparisons" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Spring offers" })).toHaveAttribute("href", "/offers/compare/c1");
    await user.click(screen.getByRole("button", { name: "Restore: Spring offers" }));
    expect(await screen.findByText(/"Spring offers" restored to your active comparisons, unchanged\./)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("link", { name: "Spring offers" })).not.toBeInTheDocument());
    expect(writes.at(-1)).toBe("POST /api/v1/me/offer-comparisons/c1/unarchive");
  });

  it("moves focus to the list's heading when the last one is archived, and says the list is empty", async () => {
    comparisons([summary("c1", "Only one")]);
    const { user } = renderApp("/offers/compare", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Archive: Only one" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Your comparisons" })).toHaveFocus());
    expect(screen.getByText("No active comparisons.")).toBeInTheDocument();
  });

  it("opens an archived comparison with a banner, and Restore changes only the flag", async () => {
    const doc = { title: "Spring offers", offers: [], factors: [], conversions: [], weights_on: false, show_in: null };
    const archived: OfferComparison = { id: "c1", revision: 4, doc, derived: { offers: [], mixed_currencies: false, currency_note: null, not_estimated: "", weighted: null }, applications: {}, archived: true, created_at: now(), updated_at: now() };
    comparisons([summary("c1", "Spring offers", true)]);
    server.use(http.get(`${API}/api/v1/me/offer-comparisons/c1`, () => HttpResponse.json(archived)));
    trackWrites();
    const { user } = renderApp("/offers/compare/c1", { signedIn: true });
    const banner = await screen.findByText(/Archived: it's out of your active list, kept exactly as it is\. Nothing was deleted\./, undefined, { timeout: 3000 });
    await user.click(within(banner.closest("p")!).getByRole("button", { name: "Restore" }));
    await waitFor(() => expect(screen.queryByText(/Archived: it's out of your active list/)).not.toBeInTheDocument());
    expect(writes).toEqual(["POST /api/v1/me/offer-comparisons/c1/unarchive"]); // no save
  });
});

describe("Archiving an application with an interview still to come", () => {
  const app = (over: Partial<Application> = {}): Application => ({
    id: "a1", employer: "Mercy General", role_title: "Ward nurse", stage: "interviewing", applied_on: "2026-10-30", next_action: "", next_action_due: null,
    target: null, archived: false, next_event: null, updated_at: now(), link: null, notes: "", notes_revision: 1, stories: [], events: [], history: [], created_at: now(), ...over,
  });
  const event = { id: "e1", kind: "interview" as const, title: "Panel interview", on_date: "2026-12-15", local_time: null, timezone: null, starts_at: null, notes: "", created_at: now() };

  function serveApp(a: Application) {
    let current = a;
    server.use(
      http.get(`${API}/api/v1/me/applications/a1`, () => HttpResponse.json(current)),
      http.post(`${API}/api/v1/me/applications/a1/:action`, ({ params }) => {
        current = { ...current, archived: params.action === "archive" };
        return HttpResponse.json(current);
      }),
    );
  }

  it("asks first, says the interview isn't cancelled, and Keep it active sends nothing", async () => {
    serveApp(app({ events: [event], next_event: event }));
    trackWrites();
    const { user } = renderApp("/applications/a1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Archive" }, { timeout: 3000 }));
    const ask = screen.getByRole("group", { name: "Archive with an interview coming up" });
    expect(ask).toHaveTextContent(/Panel interview on .*15.* is still to come\./);
    expect(ask).toHaveTextContent("It doesn't cancel the interview or change the stage, and anything already on your schedule stays.");
    await user.click(within(ask).getByRole("button", { name: "Keep it active" }));
    expect(screen.queryByRole("group", { name: "Archive with an interview coming up" })).not.toBeInTheDocument();
    await act(() => new Promise((r) => setTimeout(r, 50)));
    expect(writes).toEqual([]);

    await user.click(screen.getByRole("button", { name: "Archive" }));
    await user.click(within(screen.getByRole("group", { name: "Archive with an interview coming up" })).getByRole("button", { name: "Archive anyway" }));
    expect(await screen.findByText(/APPLICATION · ARCHIVED/)).toBeInTheDocument();
    expect(writes).toEqual(["POST /api/v1/me/applications/a1/archive"]); // the stage isn't touched
  });

  it("archives at once when nothing is coming up", async () => {
    serveApp(app());
    trackWrites();
    const { user } = renderApp("/applications/a1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Archive" }, { timeout: 3000 }));
    expect(await screen.findByText(/APPLICATION · ARCHIVED/)).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Archive with an interview coming up" })).not.toBeInTheDocument();
    expect(writes).toEqual(["POST /api/v1/me/applications/a1/archive"]);
  });
});
