import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { AcceptedAction, DisputeNote, ScheduleEntry } from "@/api/types";
import { browserTimeZone, todayIn } from "@/features/applications/dates";

import { makePlan, planItems, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

/**
 * Disputed feedback (Volume 12, prompt 7; docs/DISPUTES.md): what the plan withheld or derived from
 * a disputed point is labelled with the dispute one click away, and commitments the learner made
 * stay where they are. (The flag panel's dispute and reinstate: answerReview.test.tsx.)
 */
const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const POINT = "Backs it up with a concrete example";
const NOTE: DisputeNote = {
  text: `Based on feedback you disputed on 3 November: “${POINT}”.`, href: "/careers/registered-nurse/questions/e-good-0?answer=a-1",
  answer_id: "a-1", criterion: POINT,
};

describe("The plan, commitments and the schedule", () => {
  it("labels a step derived from a disputed point and lists what it didn't suggest, with each dispute linked", async () => {
    asNurse();
    const derived = { ...planItems[1]!, disputed: NOTE };
    const items = planItems.map((i) => (i.id === derived.id ? derived : i));
    server.use(http.get(`${API}/api/v1/me/plan`, () => HttpResponse.json({
      ...makePlan(15, items),
      withheld: [
        { text: `Not suggested: adding “${POINT}” to “What good patient assessment looks like”: you disputed this point on 3 November.`, href: NOTE.href, reinstated: false },
        { text: "Not suggested: retrying “Keeping patients informed”: you disputed that feedback on 2 November.", href: "/careers/registered-nurse/questions/e-inform-0?answer=a-2", reinstated: true },
      ],
    })));
    renderApp("/plan", { signedIn: true });
    const cards = await screen.findAllByRole("article", { name: derived.title });
    for (const card of cards) {
      expect(card).toHaveTextContent(NOTE.text);
      expect(within(card).getByRole("link", { name: "See the dispute" })).toHaveAttribute("href", NOTE.href);
    }
    const others = screen.getAllByRole("article").filter((a) => !cards.includes(a));
    expect(others.length).toBeGreaterThan(0);
    for (const other of others) expect(other.textContent).not.toMatch(/disputed/); // only the derived one
    const withheld = screen.getByRole("region", { name: /Not suggested \(2\)/ });
    expect(withheld).toHaveTextContent("Left out because of feedback you disputed, not because there's nothing to practise.");
    expect(withheld).toHaveTextContent(`Not suggested: adding “${POINT}”`);
    expect(withheld).toHaveTextContent("You've counted it again since: it can come back when your plan next updates.");
  });

  it("an accepted improvement and its scheduled occurrence stay, labelled", async () => {
    asNurse();
    const action: AcceptedAction = {
      id: "act-1", title: "Explains what you personally did", notes: "", practice_href: "/interviews/iv-r/retry/1", practice_label: "Retry",
      recurrence: "once", status: "open", done_at: null,
      source: { kind: "interview_improvement", interview_id: "iv-r", key: "point:Explains what you personally did", label: "Explains what you personally did", why: "Say “I”.", interview_title: "Registered Nurse interview", interview_date: "2026-11-03T09:00:00Z", versions: [], available: true },
      occurrences: [{ id: "occ-1", on_date: "2026-11-20", all_day: true, local_time: null, timezone: null, starts_at: null, status: "scheduled", sequence: 0, completed_at: null }],
      attempts_since: 0, revision: 1, save_replay: null, created_at: "2026-11-03T09:00:00Z", updated_at: "2026-11-03T09:00:00Z",
      disputed: { ...NOTE, text: "Based on feedback you disputed on 4 November: “Explains what you personally did”." },
    };
    server.use(http.get(`${API}/api/v1/me/actions`, () => HttpResponse.json([action])));
    renderApp("/plan", { signedIn: true });
    const item = (await screen.findByText(/From your Registered Nurse interview/)).closest("li, article") as HTMLElement;
    expect(item).toHaveTextContent("Based on feedback you disputed on 4 November");
    expect(item).toHaveTextContent("It stays as it is; it's yours to keep, move or mark done.");
    expect(within(item).getByRole("button", { name: /Mark done/ })).toBeEnabled();
  });

  it("a scheduled entry derived from a disputed point is labelled and still scheduled", async () => {
    asNurse();
    const device = browserTimeZone();
    const day = todayIn(device);
    server.use(
      http.get(`${API}/api/v1/me/schedule/settings`, () => HttpResponse.json({ timezone: null, reminders: false, reminder_minutes: 10, quiet_start: null, quiet_end: null })),
      http.get(`${API}/api/v1/me/schedule/schedulable`, () => HttpResponse.json([])),
    );
    const entry: ScheduleEntry = {
      id: "e1", uid: "u1@codecoach", kind: "plan_item", ref: "item-retry", title: "Retry: What good patient assessment looks like", href: "/plan",
      all_day: true, on_date: day, local_time: null, timezone: null, starts_at: null, ends_at: null, duration_min: 30, status: "scheduled",
      done_at: null, available: true, conflicts: [], sequence: 0, notes: "", created_at: new Date().toISOString(), follows_interview: false, disputed: NOTE,
    };
    server.use(http.get(`${API}/api/v1/me/schedule`, () => HttpResponse.json([entry])));
    renderApp("/schedule", { signedIn: true });
    const row = (await screen.findByText(entry.title)).closest("li") as HTMLElement;
    await waitFor(() => expect(row).toHaveTextContent(NOTE.text));
    expect(row).not.toHaveTextContent("Cancelled");
    expect(within(row).getByRole("link", { name: "See the dispute" })).toHaveAttribute("href", NOTE.href);
  });
});
