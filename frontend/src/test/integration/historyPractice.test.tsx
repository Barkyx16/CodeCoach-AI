/**
 * Drills, whiteboard designs and work samples in History (Volume 16, prompt 6;
 * docs/COMPARING_ATTEMPTS.md): each attempt's row says what was practised, its result and its
 * comparison in its own page's words, and its in-app help, asked for with the rows on screen.
 */
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ActivityItem, AttemptConditions } from "@/api/types";

import { renderApp } from "../render";
import { API, server } from "../server";

const NOTE = "Only help shown in CodeCoach is recorded. Help from anywhere else isn't known, and accessibility settings such as dictation or captions are never counted as help.";
const hinted: AttemptConditions = {
  labels: ["Hint shown"], help: [{ label: "Hint shown", detail: "Lesson “STAR answers” read", at: "2026-11-16T09:00:00Z" }],
  recorded_from: "2026-11-15", note: NOTE, round: null, interview: null, unrecorded: null,
};
const row = (id: string, type: ActivityItem["type"], title: string, detail: string, href: string): ActivityItem => ({
  id: `${type}:${id}`, type, occurred_at: new Date().toISOString(), career: "registered-nurse", career_title: "Registered Nurse",
  title, detail, skills: [], status: "completed", status_label: "Completed", score: null, session_id: null,
  target: { href, attempt_id: id },
});
const rows = [
  row("d-2", "drill_attempt", "Answer with a concrete example", "3 of 4 points there · Comparable with the one before", "/drills/example"),
  row("d-1", "drill_attempt", "Answer with a concrete example", "2 of 4 points there · Not compared: the first checked attempt at this drill", "/drills/example"),
  row("w-1", "whiteboard_attempt", "Design a URL shortener", "4 of 6 points addressed · Not compared: the first checked attempt at this prompt", "/whiteboard/sd-url-shortener"),
];

describe("Drills, whiteboard designs and work samples in History", () => {
  it("lists each attempt with its result, its comparison and its in-app help", async () => {
    const asked: unknown[] = [];
    server.use(
      http.get(`${API}/api/v1/me/activity`, () => HttpResponse.json({ items: rows, total: rows.length, page: 1, page_size: 20 })),
      http.post(`${API}/api/v1/me/attempt-conditions`, async ({ request }) => {
        asked.push(await request.json());
        return HttpResponse.json({ submissions: {}, answers: {}, drill_attempts: { "d-2": hinted }, whiteboard_attempts: {} });
      }),
    );
    renderApp("/history", { signedIn: true });
    const second = (await screen.findByText(/Comparable with the one before/)).closest("a")!;
    expect(second).toHaveAttribute("href", "/drills/example");
    expect(second).toHaveTextContent("Drill");
    expect(second).toHaveTextContent("3 of 4 points there");
    await waitFor(() => expect(second).toHaveTextContent("In-app help: Hint shown"));
    const first = screen.getAllByText(/Not compared: the first checked attempt at this drill/)[0]!.closest("a")!;
    expect(first.textContent).not.toMatch(/In-app help/); // none came back for it
    expect(screen.getByText(/Not compared: the first checked attempt at this prompt/).closest("a")).toHaveTextContent("Whiteboard");
    expect(asked).toEqual([{ submission_ids: [], answer_ids: [], interview_ids: [], drill_attempt_ids: ["d-2", "d-1"], whiteboard_attempt_ids: ["w-1"] }]);
  });
});
