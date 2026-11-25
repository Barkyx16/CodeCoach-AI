/**
 * Hints inside the coding interview (Volume 17, prompt 4; docs/ATTEMPT_CONDITIONS.md): the panel
 * offers the problem's ladder one level at a time, shows what the coach reads first (the code last
 * sent), asks bound to that preview, and lists each hint the interview recorded with its time and
 * message count; it's closed once time is up.
 */
import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { CoachPreview, Interview, InterviewHintRecord } from "@/api/types";

import { renderApp } from "../render";
import { API, server } from "../server";

const live = (hints: InterviewHintRecord[] = [], seconds = 900): Interview => ({
  id: "iv-1", kind: "coding", questions: [], status: "in_progress", phase: "coding", phase_index: 2, phase_guide: "Write the code.",
  problem: { slug: "two-sum", title: "Two Sum", difficulty: "easy" }, duration_seconds: 900, started_at: new Date().toISOString(),
  deadline_at: new Date(Date.now() + seconds * 1000).toISOString(), ended_at: null, seconds_remaining: seconds, candidate_turns_remaining: 28,
  provider: "offline", final_code: "class Solution {}", evaluation: null, hints,
  turns: [{ seq: 0, role: "interviewer", phase: "clarify", content: "Hi!", created_at: new Date().toISOString(), skipped: false }],
});
const preview = (fp: string): CoachPreview => ({
  operation: "hint", about: ["A level 1 hint."], already_answered: null,
  items: [{ key: "code", label: "Your code", source: "The code you last sent in the interview.", text: "class Solution {}", derived: false, required: true, why_required: null, notes: [], names_replaced: 0 }],
  left_out: [], required_public: [], instructions: "CodeCoach's own instructions.", recipient: "The built-in coach, on CodeCoach's own server: nothing leaves it",
  recipient_kind: "built_in", fallback: null, remaining_today: 48, context_fingerprint: fp, names_replaced: 0, names_note: null,
});
const RECORD: InterviewHintRecord = { level: 1, level_name: "Nudge", at: "2026-11-16T09:10:00Z", turn: 3 };

describe("Hints inside the coding interview", () => {
  it("checks what the coach reads, asks bound to it, and lists the recorded hint", async () => {
    let iv = live();
    const asked: unknown[] = [];
    const previewed: unknown[] = [];
    server.use(
      http.get(`${API}/api/v1/interviews/iv-1`, () => HttpResponse.json(iv)),
      http.post(`${API}/api/v1/ai/hint/preview`, async ({ request }) => { previewed.push(await request.json()); return HttpResponse.json(preview("v1:hint")); }),
      http.post(`${API}/api/v1/interviews/iv-1/hint`, async ({ request }) => {
        asked.push(await request.json());
        iv = live([RECORD]);
        return HttpResponse.json({ hint: { level: 1, level_name: "Nudge", content: { hint: "What could you remember as you go?", focus_area: null, encouragement: null }, max_level: 4, next_level_available: true, provider: "offline", grounded: true }, record: RECORD, repeated: false });
      }),
      http.get(`${API}/api/v1/me/ai/history`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50 })),
    );
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    await user.click(await screen.findByText("Hints"));
    await user.click(screen.getByRole("button", { name: "Get a hint" }));
    expect(previewed).toEqual([{ problem_slug: "two-sum", source_code: "class Solution {}", level: 1 }]);
    await user.click(await screen.findByRole("button", { name: "Ask for the level 1 hint" }));
    const list = await screen.findByRole("list", { name: "Hints in this interview" });
    expect(within(list).getByText("Level 1 · Nudge")).toBeInTheDocument();
    expect(list).toHaveTextContent("after 3 messages");
    expect(await within(list).findByText("What could you remember as you go?")).toBeInTheDocument();
    expect(asked).toEqual([{ level: 1, approved_context: "v1:hint" }]);
    expect(screen.getByRole("button", { name: "Unlock level 2: Concept" })).toBeInTheDocument();
  });

  it("is closed once the time is up, and asks nothing", async () => {
    const asked: unknown[] = [];
    server.use(
      http.get(`${API}/api/v1/interviews/iv-1`, () => HttpResponse.json(live([RECORD], 0))),
      http.post(`${API}/api/v1/interviews/iv-1/hint`, () => { asked.push(1); return HttpResponse.json({}, { status: 500 }); }),
      http.get(`${API}/api/v1/me/ai/history`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50 })),
    );
    renderApp("/interviews/iv-1", { signedIn: true });
    expect(await screen.findByText("Hints are closed: the interview is over.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Get a hint|Unlock level/ })).not.toBeInTheDocument();
    expect(asked).toEqual([]);
  });
});
