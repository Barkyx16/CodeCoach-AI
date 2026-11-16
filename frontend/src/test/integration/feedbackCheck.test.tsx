/**
 * A check made before time ran out (Volume 16, prompt 3; docs/COACH_CONTEXT.md, "A check before time
 * ran out"): after "What the feedback reads", "I've checked this" keeps the check with the interview
 * and says, once, what happens if time runs out; a check refused because the interview moved on (from
 * another tab) says why and shows what it reads now; the review says whether a time-out read what was
 * checked, with the time.
 */
import { render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { CoachPreview, FeedbackRead, Interview } from "@/api/types";
import { FeedbackReadSection } from "@/features/review/FeedbackRead";

import { renderApp } from "../render";
import { API, server } from "../server";

const KEPT = "Checked. If time runs out before you finish, the review will say you checked this, or name what changed after.";
const MOVED_ON = "What the feedback would read changed since you checked it (a message was sent or your code changed, perhaps in another tab), so this check wasn't kept. Check what it reads now.";

const running = (): Interview => ({
  id: "iv-1", kind: "coding", questions: [], status: "in_progress", phase: "coding", phase_index: 2, phase_guide: "Write the code.",
  problem: { slug: "two-sum", title: "Two Sum", difficulty: "easy" }, duration_seconds: 900, started_at: new Date().toISOString(),
  deadline_at: new Date(Date.now() + 900_000).toISOString(), ended_at: null, seconds_remaining: 900, candidate_turns_remaining: 29,
  provider: "offline", final_code: null, evaluation: null,
  turns: [{ seq: 0, role: "interviewer", phase: "clarify", content: "Hi! Tell me how you understand the problem.", created_at: new Date().toISOString(), skipped: false }],
});

const feedbackPreview = (fingerprint: string, conversation = "[clarify] INTERVIEWER: Hi!"): CoachPreview => ({
  operation: "interview_feedback", about: ["Feedback on the whole interview, scored on the rubric's dimensions."], already_answered: null,
  items: [
    { key: "conversation", label: "The conversation so far", source: "Every message in this interview, in order.", text: conversation,
      derived: false, required: true, why_required: "The feedback is on the whole interview.", notes: [], names_replaced: 0 },
    { key: "code", label: "Your code", source: "As in the editor.", text: "class Solution {}", derived: false, required: true, why_required: null, notes: [], names_replaced: 0 },
    { key: "ending", label: "How it ended", source: "Worked out by CodeCoach.", text: "How it ended: finished.", derived: true, required: true, why_required: null, notes: [], names_replaced: 0 },
  ],
  left_out: [], required_public: [], instructions: "CodeCoach's own instructions.", recipient: "The built-in interviewer, on CodeCoach's own server: nothing leaves it",
  recipient_kind: "built_in", fallback: null, remaining_today: 48, context_fingerprint: fingerprint, names_replaced: 0, names_note: null,
});

function serve(confirm: (body: Record<string, unknown>) => Response) {
  const confirmed: Record<string, unknown>[] = [];
  server.use(
    http.get(`${API}/api/v1/interviews/iv-1`, () => HttpResponse.json(running())),
    http.post(`${API}/api/v1/interviews/iv-1/feedback/preview`, () => HttpResponse.json(feedbackPreview("v1:first"))),
    http.post(`${API}/api/v1/interviews/iv-1/feedback/confirm`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      confirmed.push(body);
      return confirm(body);
    }),
  );
  return confirmed;
}

describe("A check before time ran out", () => {
  it("I've checked this keeps the check, sends nothing else and says once what a time-out will do", async () => {
    const confirmed = serve(() => HttpResponse.json({ at: "2026-11-16T09:13:00Z", fingerprint: "v1:first", labels: ["The conversation so far", "Your code"], text: KEPT }));
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    expect(screen.queryByRole("button", { name: "I've checked this" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "What the feedback reads" }));
    await screen.findByRole("region", { name: "What the interviewer reads" });
    await user.click(screen.getByRole("button", { name: "I've checked this" }));
    const said = await screen.findAllByText(KEPT);
    expect(said).toHaveLength(1);
    expect(said[0]).toHaveAttribute("role", "status");
    expect(confirmed).toEqual([expect.objectContaining({ ending: "finished", approved_context: "v1:first" })]);
    // The interview stays open: the panel is still there to finish from.
    expect(screen.getByRole("region", { name: "What the interviewer reads" })).toBeInTheDocument();
  });

  it("a check refused because the interview moved on says why and shows what it reads now", async () => {
    serve(() => HttpResponse.json({ error: { code: "context_changed", message: MOVED_ON,
      details: { preview: feedbackPreview("v1:second", "[clarify] CANDIDATE: Sent from the other tab.") } } }, { status: 409 }));
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "What the feedback reads" }));
    await user.click(await screen.findByRole("button", { name: "I've checked this" }));
    const box = await screen.findByRole("region", { name: "What the interviewer reads" });
    expect(await within(box).findByText(MOVED_ON)).toBeInTheDocument();
    expect(within(box).getByLabelText("Exactly what's sent: The conversation so far")).toHaveTextContent("Sent from the other tab.");
    expect(screen.queryByText(KEPT)).not.toBeInTheDocument();
  });

  it("the review says a time-out read what was checked, with the time, or names what changed", () => {
    const base: FeedbackRead = {
      recorded: true, ending: "time_expired", checked: false, fingerprint: "v1:read", read_by: "The built-in interviewer", items: [],
      text: "You checked this before time ran out.",
      confirmed: { at: "2026-11-16T09:13:00Z", fingerprint: "v1:first", matched: true, changed: [], code_unsent: false },
    };
    const { unmount } = render(<FeedbackReadSection read={base} />);
    const section = screen.getByRole("region", { name: "What the feedback read" });
    expect(section).toHaveTextContent("You checked this before time ran out.");
    expect(within(section).getByText((_, el) => el?.tagName === "TIME")).toHaveAttribute("dateTime", "2026-11-16T09:13:00Z");
    unmount();
    render(<FeedbackReadSection read={{ ...base, text: "You checked an earlier version before time ran out; it changed after: The conversation so far.",
      confirmed: { ...base.confirmed!, matched: false, changed: ["The conversation so far"] } }} />);
    expect(screen.getByRole("region", { name: "What the feedback read" })).toHaveTextContent("it changed after: The conversation so far.");
  });

  it("says what changed in each part after the check, with the added lines read from the kept code (Volume 17, prompt 1)", () => {
    const code = ["class Solution {", "  int[] twoSum(int[] nums, int target) {", "    var seen = new java.util.HashMap<Integer, Integer>();", "    return null;", "  }", "}"].join("\n");
    const read: FeedbackRead = {
      recorded: true, ending: "time_expired", checked: false, fingerprint: "v1:read", read_by: null, items: [],
      text: "You checked an earlier version before time ran out; it changed after: The conversation so far, Your code.",
      confirmed: {
        at: "2026-11-16T09:13:00Z", fingerprint: "v1:first", matched: false, changed: ["The conversation so far", "Your code"], code_unsent: false,
        changes: [
          { label: "The conversation so far", text: "The conversation so far: 2 messages sent after your check", messages_after: 2, added: null, removed: null, added_lines: [] },
          { label: "Your code", text: "Your code: 1 line added, 2 lines removed", added: 1, removed: 2, added_lines: [3], messages_after: null },
        ],
      },
    };
    render(<FeedbackReadSection read={read} code={code} />);
    const list = screen.getByRole("list", { name: "What changed after your check" });
    expect(within(list).getAllByRole("listitem").map((li) => li.textContent?.split("\n")[0])).toEqual([
      "The conversation so far: 2 messages sent after your check.",
      expect.stringContaining("Your code: 1 line added, 2 lines removed."),
    ]);
    const lines = within(list).getByLabelText("Lines added to Your code after your check");
    expect(lines).toHaveTextContent("3 var seen = new java.util.HashMap<Integer, Integer>();");
    expect(lines).not.toHaveTextContent("return null");
  });

  it("a check kept before this says only the labels, and without the code no lines are shown", () => {
    const read: FeedbackRead = {
      recorded: true, ending: "time_expired", checked: false, fingerprint: "v1:read", read_by: null, items: [],
      text: "You checked an earlier version before time ran out; it changed after: Your code.",
      confirmed: { at: "2026-11-16T09:13:00Z", fingerprint: "v1:first", matched: false, changed: ["Your code"], code_unsent: false, changes: [] },
    };
    const { unmount } = render(<FeedbackReadSection read={read} code="int x;" />);
    expect(screen.queryByRole("list", { name: "What changed after your check" })).not.toBeInTheDocument();
    unmount();
    render(<FeedbackReadSection read={{ ...read, confirmed: { ...read.confirmed!, changes: [{ label: "Your code", text: "Your code: 1 line added", added: 1, removed: 0, added_lines: [1], messages_after: null }] } }} />);
    expect(screen.getByRole("list", { name: "What changed after your check" })).toHaveTextContent("Your code: 1 line added.");
    expect(screen.queryByLabelText("Lines added to Your code after your check")).not.toBeInTheDocument();
  });

  it("a hint asked for after the check is listed among what changed, with no lines (Volume 18, prompt 3)", () => {
    const read: FeedbackRead = {
      recorded: true, ending: "time_expired", checked: false, fingerprint: "v1:read", read_by: null, items: [],
      text: "You checked an earlier version before time ran out; it changed after: Hints.",
      confirmed: {
        at: "2026-11-16T09:13:00Z", fingerprint: "v1:first", matched: false, changed: ["Hints"], code_unsent: false,
        changes: [{ label: "Hints", text: "Hints: level 2 (concept) asked for after your check", hints_after: ["level 2 (concept)"], added: null, removed: null, added_lines: [], messages_after: null }],
      },
    };
    render(<FeedbackReadSection read={read} code="class Solution {}" />);
    const list = screen.getByRole("list", { name: "What changed after your check" });
    expect(within(list).getByRole("listitem")).toHaveTextContent(/^Hints: level 2 \(concept\) asked for after your check\.$/);
    expect(screen.queryByLabelText(/^Lines added to/)).not.toBeInTheDocument();
  });
});
