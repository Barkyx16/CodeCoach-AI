import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { AcceptedAction, Impact, LifecycleOutcome } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

/**
 * Archiving and deleting an accepted improvement from the plan page (Volume 14, prompt 5;
 * docs/ACCEPTED_ACTIONS.md, "Archive and delete"): the server's plan is shown first; carrying it
 * out sends that plan's fingerprint; an archived one moves to "Archived" with Unarchive; a changed
 * scope shows the new plan and does nothing.
 */
const now = new Date().toISOString();
const TITLE = "Explains what you personally did";
const nurse = { ...baseUser, career_track: "registered-nurse" };
const action = (over: Partial<AcceptedAction> = {}): AcceptedAction => ({
  id: "act-1", title: TITLE, notes: "", practice_href: "/interviews/iv-r/retry/1", practice_label: "Retry “A hard shift”",
  recurrence: "weekly", status: "open", done_at: null, archived_at: null,
  source: {
    kind: "interview_improvement", interview_id: "iv-r", key: "point:x", label: TITLE, why: "Say “I” for your own actions.",
    interview_title: "Registered Nurse interview", interview_date: "2026-11-03T09:00:00Z", versions: [], available: true,
  },
  occurrences: [], attempts_since: 0, revision: 1, save_replay: null, created_at: now, updated_at: now, ...over,
});
const impact = (kind: "archive" | "delete", occurrences = 1): Impact => ({
  action: kind === "archive" ? "archive_action" : "delete_action", target_id: "act-1", title: TITLE,
  summary: kind === "archive" ? "Archive this improvement" : "Delete this improvement",
  effects: [
    { effect: kind === "archive" ? "archived" : "deleted", kind: "accepted improvement", title: TITLE, id: "act-1", note: null },
    ...Array.from({ length: occurrences }, (_, i) => ({
      effect: kind === "archive" ? "kept" as const : "deleted" as const, kind: "occurrence", title: `2026-11-${16 + 7 * i} (not done yet)`, id: `o${i}`, note: null,
    })),
    { effect: "kept", kind: "kit checklist item", title: "Kit for Panel interview", id: "ev-1", note: kind === "archive" ? "Stays, labelled archived." : "Stays on the kit's checklist as “An improvement you removed”." },
  ],
  notes: [], fingerprint: `${kind}-${occurrences}`,
});
const outcome = (i: Impact, message: string): LifecycleOutcome => ({ ...i, done_at: now, message, replayed: false, restorable_until: null });

function serve(initial: AcceptedAction[], opts: { changedOnce?: boolean } = {}) {
  let current = initial;
  let changed = opts.changedOnce ?? false;
  const sent: { path: string; body: unknown }[] = [];
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/me/actions`, () => HttpResponse.json(current)),
    http.get(`${API}/api/v1/me/actions/act-1/archive-preview`, () => HttpResponse.json(impact("archive"))),
    http.get(`${API}/api/v1/me/actions/act-1/delete-preview`, () => HttpResponse.json(impact("delete"))),
    http.post(`${API}/api/v1/me/actions/act-1/archive`, async ({ request }) => {
      sent.push({ path: "archive", body: await request.json() });
      current = [action({ archived_at: now })];
      return HttpResponse.json(outcome(impact("archive"), `Archived ${TITLE}. Unarchive it any time.`));
    }),
    http.post(`${API}/api/v1/me/actions/act-1/unarchive`, () => {
      sent.push({ path: "unarchive", body: null });
      current = [action()];
      return HttpResponse.json(current[0]);
    }),
    http.post(`${API}/api/v1/me/actions/act-1/delete`, async ({ request }) => {
      sent.push({ path: "delete", body: await request.json() });
      if (changed) {
        changed = false;
        return HttpResponse.json({ error: { code: "impact_changed", message: "Changed", request_id: "r", details: { current: impact("delete", 2) } } }, { status: 409 });
      }
      current = [];
      return HttpResponse.json(outcome(impact("delete"), `Deleted ${TITLE}.`));
    }),
  );
  return sent;
}

describe("Archiving and deleting an accepted improvement", () => {
  it("archives as previewed, then lists it under Archived with Unarchive", async () => {
    const sent = serve([action()]);
    const { user } = renderApp("/plan", { signedIn: true });
    const section = await screen.findByRole("region", { name: "Improvements you accepted (1)" });
    await user.click(within(section).getByRole("button", { name: `Archive: ${TITLE}` }));
    const plan = await within(section).findByRole("group", { name: "What this will do" });
    expect(plan).toHaveTextContent("Stays, labelled archived.");
    await user.click(within(plan).getByRole("button", { name: "Archive this improvement" }));
    expect(await screen.findByText(`Archived ${TITLE}. Unarchive it any time.`)).toBeInTheDocument();
    expect(sent[0]).toMatchObject({ path: "archive", body: { expected_fingerprint: "archive-1" } });
    const now = await screen.findByRole("region", { name: "Improvements you accepted (0)" });
    expect(now).toHaveTextContent("Archived (1)");
    await user.click(within(now).getByText("Archived (1)"));
    expect(within(now).queryByRole("button", { name: `Archive: ${TITLE}` })).toBeNull();
    expect(within(now).queryByRole("button", { name: /Add weeks to your schedule/ })).toBeNull();
    await user.click(within(now).getByRole("button", { name: `Unarchive: ${TITLE}` }));
    expect(await screen.findByRole("region", { name: "Improvements you accepted (1)" })).toBeInTheDocument();
    expect(sent.map((s) => s.path)).toEqual(["archive", "unarchive"]);
  });

  it("deletes as previewed and says so where the list is", async () => {
    const sent = serve([action()]);
    const { user } = renderApp("/plan", { signedIn: true });
    const section = await screen.findByRole("region", { name: "Improvements you accepted (1)" });
    await user.click(within(section).getByRole("button", { name: `Delete: ${TITLE}` }));
    const plan = await within(section).findByRole("group", { name: "What this will do" });
    expect(plan).toHaveTextContent("Stays on the kit's checklist as “An improvement you removed”.");
    await user.click(within(plan).getByRole("button", { name: "Delete this improvement" }));
    expect(await screen.findByText(`Deleted ${TITLE}.`)).toBeInTheDocument();
    expect(sent).toEqual([{ path: "delete", body: expect.objectContaining({ expected_fingerprint: "delete-1" }) }]);
  });

  it("a scope that changed since the preview shows the new plan and does nothing", async () => {
    const sent = serve([action()], { changedOnce: true });
    const { user } = renderApp("/plan", { signedIn: true });
    const section = await screen.findByRole("region", { name: "Improvements you accepted (1)" });
    await user.click(within(section).getByRole("button", { name: `Delete: ${TITLE}` }));
    const plan = await within(section).findByRole("group", { name: "What this will do" });
    await user.click(within(plan).getByRole("button", { name: "Delete this improvement" }));
    expect(await within(section).findByText(/What this affects changed since you looked/)).toBeInTheDocument();
    expect(within(section).getByText("2026-11-23 (not done yet)")).toBeInTheDocument();
    expect(screen.queryByText(`Deleted ${TITLE}.`)).toBeNull();
    // Carrying out the new plan sends its own fingerprint.
    await user.click(within(section).getByRole("button", { name: "Delete this improvement" }));
    await waitFor(() => expect(sent).toHaveLength(2));
    expect(sent[1]).toMatchObject({ body: { expected_fingerprint: "delete-2" } });
  });
});
