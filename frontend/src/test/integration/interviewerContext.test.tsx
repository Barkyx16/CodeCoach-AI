import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { CoachPreview, Interview } from "@/api/types";
import { CHECK_EACH_KEY, INTERVIEWER_REFUSED, MESSAGE_CHANGED } from "@/features/interview/interviewerCheck";

import { renderApp } from "../render";
import { API, server } from "../server";

/**
 * What the coding interviewer reads (Volume 14, prompt 3; docs/COACH_CONTEXT.md, "The coding
 * interviewer"): one action away, or before every message and the feedback when the learner turns
 * that on (kept on this device); a checked request is sent bound to the preview, and a refusal
 * shows what would be read now.
 */
const base = (): Interview => ({
  id: "iv-1", kind: "coding", questions: [], status: "in_progress", phase: "clarify", phase_index: 0,
  phase_guide: "Restate the problem and ask clarifying questions about inputs, outputs and edge cases.",
  problem: { slug: "two-sum", title: "Two Sum", difficulty: "easy" },
  duration_seconds: 1800, started_at: new Date().toISOString(),
  deadline_at: new Date(Date.now() + 1800_000).toISOString(), ended_at: null,
  seconds_remaining: 1800, candidate_turns_remaining: 30, provider: "offline",
  turns: [{ seq: 0, role: "interviewer", phase: "clarify", content: "Hi! Tell me how you understand the problem.", created_at: new Date().toISOString(), skipped: false }],
  final_code: null, evaluation: null,
});

const preview = (over: { message?: string; code?: string; fingerprint?: string; feedback?: "finished" | "abandoned" } = {}): CoachPreview => ({
  operation: over.feedback ? "interview_feedback" : "interview_message",
  about: over.feedback ? ["Feedback on the whole interview, scored on the rubric's dimensions."] : ["Your message 1 of the 30 an interview allows."],
  already_answered: null,
  items: [
    ...(over.feedback ? [] : [{ key: "message" as const, label: "Your message", source: "As you wrote it: 24 characters.",
      text: over.message ?? "My token was [REDACTED].", derived: false, required: true, why_required: "It's what the interviewer answers.",
      notes: ["1 secret-looking string replaced with [REDACTED]."], names_replaced: 0 }]),
    { key: "conversation", label: "The conversation so far", source: "Every message in this interview, in order.",
      text: "[clarify] INTERVIEWER: Hi! Tell me how you understand the problem.", derived: false, required: true,
      why_required: "The interviewer answers in the context of what's been said.", notes: [], names_replaced: 0 },
    { key: "code", label: "Your code", source: "As in the editor when you checked: 3 lines. Sent with line numbers added.",
      text: over.code ?? "class Solution {}", derived: false, required: true, why_required: "The interviewer reads your code as it stands with each message.", notes: [], names_replaced: 0 },
    ...(over.feedback ? [{ key: "ending" as const, label: "How it ended", source: "Worked out by CodeCoach from how you're ending it.",
      text: `How it ended: ${over.feedback}.`, derived: true, required: true, why_required: null, notes: [], names_replaced: 0 }] : []),
  ],
  left_out: [],
  required_public: ["The problem “Two Sum”: its statement, constraints, method signature and expected complexity."],
  instructions: "CodeCoach's own instructions to the interviewer, the same for everyone. They aren't shown here.",
  recipient: "The built-in interviewer, on CodeCoach's own server: nothing leaves it",
  recipient_kind: "built_in", fallback: null, remaining_today: 48,
  context_fingerprint: over.fingerprint ?? "v1:interviewer",
  names_replaced: 0,
  names_note: null,
});

function interviewServer(opts: { refuse?: CoachPreview } = {}) {
  let iv = base();
  const previews: Record<string, unknown>[] = [];
  const posted: Record<string, unknown>[] = [];
  const finished: Record<string, unknown>[] = [];
  const abandoned: unknown[] = [];
  server.use(
    http.get(`${API}/api/v1/interviews/iv-1`, () => HttpResponse.json(iv)),
    http.post(`${API}/api/v1/interviews/iv-1/message/preview`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      previews.push(body);
      return HttpResponse.json(preview({ message: String(body.message), code: String(body.code) }));
    }),
    http.post(`${API}/api/v1/interviews/iv-1/feedback/preview`, async ({ request }) => {
      const body = (await request.json()) as { ending: "finished" | "abandoned" };
      previews.push(body);
      return HttpResponse.json(preview({ feedback: body.ending, fingerprint: `v1:${body.ending}` }));
    }),
    http.post(`${API}/api/v1/interviews/iv-1/messages`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      posted.push(body);
      if (opts.refuse) {
        return HttpResponse.json({ error: { code: "context_changed", message: "What the interviewer would read changed since you checked it, so nothing was sent.", details: { preview: opts.refuse } } }, { status: 409 });
      }
      const n = iv.turns.length;
      iv = { ...iv, candidate_turns_remaining: iv.candidate_turns_remaining - 1, turns: [...iv.turns,
        { seq: n, role: "candidate", phase: "clarify", content: String(body.message), created_at: new Date().toISOString(), skipped: false },
        { seq: n + 1, role: "interviewer", phase: "clarify", content: "What would you store?", created_at: new Date().toISOString(), skipped: false }] };
      return HttpResponse.json(iv);
    }),
    http.post(`${API}/api/v1/interviews/iv-1/finish`, async ({ request }) => {
      finished.push((await request.json()) as Record<string, unknown>);
      iv = { ...iv, status: "completed", phase: null, ended_at: new Date().toISOString() };
      return HttpResponse.json(iv);
    }),
    http.post(`${API}/api/v1/interviews/iv-1/abandon`, async ({ request }) => {
      abandoned.push(await request.json().catch(() => null));
      iv = { ...iv, status: "abandoned", phase: null, ended_at: new Date().toISOString() };
      return HttpResponse.json(iv);
    }),
  );
  return { previews, posted, finished, abandoned };
}

const panel = () => screen.findByRole("region", { name: "What the interviewer reads" });

describe("What the coding interviewer reads", () => {
  it("is one action away, and a checked message goes bound to what was shown", async () => {
    const { previews, posted } = interviewServer();
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "My token was secret.");
    await user.click(screen.getByRole("button", { name: "What the interviewer reads" }));
    const box = await panel();
    expect(within(box).getByText("Your message")).toBeInTheDocument();
    expect(within(box).getByText("1 secret-looking string replaced with [REDACTED].")).toBeInTheDocument();
    expect(within(box).getByLabelText("Exactly what's sent: The conversation so far")).toHaveTextContent("[clarify] INTERVIEWER: Hi!");
    expect(within(box).getByText(/The built-in interviewer, on CodeCoach's own server: nothing leaves it/)).toBeInTheDocument();
    expect(posted).toEqual([]); // checking sends nothing
    await user.click(within(box).getByRole("button", { name: "Send to the interviewer" }));
    expect(await screen.findByText("What would you store?")).toBeInTheDocument();
    expect(posted[0]).toMatchObject({ message: "My token was secret.", approved_context: "v1:interviewer", code: previews[0]!.code });
    expect(screen.queryByRole("region", { name: "What the interviewer reads" })).not.toBeInTheDocument();
  });

  it("without the setting, Send goes straight away, as before, unbound", async () => {
    const { previews, posted } = interviewServer();
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Can the input be empty?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("What would you store?")).toBeInTheDocument();
    expect(previews).toEqual([]);
    expect(posted[0]).not.toHaveProperty("approved_context");
  });

  it("with the every-message setting on (kept on this device), Send shows the check first", async () => {
    const { posted } = interviewServer();
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    await user.click(await screen.findByLabelText(/Check every message, and the feedback, before it's sent/));
    expect(localStorage.getItem(CHECK_EACH_KEY)).toBe("on");
    await user.type(screen.getByLabelText("Your answer"), "Is the array sorted?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    const box = await panel();
    expect(posted).toEqual([]);
    expect(screen.getByLabelText("Your answer")).toHaveValue("Is the array sorted?");
    await user.click(within(box).getByRole("button", { name: "Send to the interviewer" }));
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0]).toMatchObject({ message: "Is the array sorted?", approved_context: "v1:interviewer" });
  });

  it("the setting is read back on the next visit", async () => {
    localStorage.setItem(CHECK_EACH_KEY, "on");
    interviewServer();
    renderApp("/interviews/iv-1", { signedIn: true });
    expect(await screen.findByLabelText(/Check every message, and the feedback, before it's sent/)).toBeChecked();
  });

  it("a message changed after checking can't be sent until it's checked again", async () => {
    interviewServer();
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    const answer = await screen.findByLabelText("Your answer");
    await user.type(answer, "First words.");
    await user.click(screen.getByRole("button", { name: "What the interviewer reads" }));
    const box = await panel();
    await user.type(answer, " More.");
    expect(within(box).getByText(new RegExp(MESSAGE_CHANGED.replace(/[.?]/g, "\\$&")))).toBeInTheDocument();
    expect(within(box).getByRole("button", { name: "Send to the interviewer" })).toBeDisabled();
    await user.click(within(box).getByRole("button", { name: "Check again" }));
    await waitFor(() => expect(within(box).getByLabelText("Exactly what's sent: Your message")).toHaveTextContent("First words. More."));
    expect(within(box).getByRole("button", { name: "Send to the interviewer" })).toBeEnabled();
  });

  it("a refused message shows what the interviewer would read now and keeps the text", async () => {
    const { posted } = interviewServer({ refuse: preview({ code: "class Solution { /* now */ }", fingerprint: "v1:now" }) });
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Here goes.");
    await user.click(screen.getByRole("button", { name: "What the interviewer reads" }));
    await user.click(within(await panel()).getByRole("button", { name: "Send to the interviewer" }));
    const box = await panel();
    expect(await within(box).findByText(INTERVIEWER_REFUSED)).toBeInTheDocument();
    expect(within(box).getByLabelText("Exactly what's sent: Your code")).toHaveTextContent("/* now */");
    expect(screen.getByLabelText("Your answer")).toHaveValue("Here goes.");
    expect(posted).toHaveLength(1);
    expect(screen.queryByText("What would you store?")).not.toBeInTheDocument();
  });

  it("the feedback is checked the same way, on Finish and on End early", async () => {
    const { finished, abandoned } = interviewServer();
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "What the feedback reads" }));
    let box = await panel();
    expect(within(box).getByLabelText("Exactly what's sent: How it ended")).toHaveTextContent("How it ended: finished.");
    expect(within(box).getByText(/The feedback uses one of the 48 coaching requests you have left today/)).toBeInTheDocument();
    await user.click(within(box).getByRole("button", { name: "Cancel" }));
    expect(screen.getByText("Cancelled. Nothing was sent.")).toBeInTheDocument();
    expect(finished).toEqual([]);

    await user.click(screen.getByLabelText(/Check every message, and the feedback, before it's sent/));
    vi.spyOn(window, "confirm").mockReturnValueOnce(true);
    await user.click(screen.getByRole("button", { name: "End early" }));
    box = await panel();
    expect(within(box).getByLabelText("Exactly what's sent: How it ended")).toHaveTextContent("How it ended: abandoned.");
    expect(abandoned).toEqual([]);
    await user.click(within(box).getByRole("button", { name: "End and get feedback" }));
    await waitFor(() => expect(abandoned).toEqual([{ approved_context: "v1:abandoned" }]));
  });

  it("Finish with the setting on sends the feedback bound to its check", async () => {
    localStorage.setItem(CHECK_EACH_KEY, "on");
    const { finished, previews } = interviewServer();
    const { user } = renderApp("/interviews/iv-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Finish & get feedback" }));
    await user.click(within(await panel()).getByRole("button", { name: "Finish and get feedback" }));
    await waitFor(() => expect(finished).toHaveLength(1));
    expect(finished[0]).toMatchObject({ approved_context: "v1:finished" });
    expect(previews[0]).toMatchObject({ ending: "finished" });
    expect(finished[0]!.code).toBe(previews[0]!.code);
  });
});
