/**
 * Comparing sample answers (Volume 10, prompt 6; docs/COMPARE_ANSWERS.md): neutral samples with no
 * explanation until a deliberate reveal, excerpts marked from the keyboard with a reason each, one
 * sample at a time on a narrow screen with the marks kept, an optional choice only when a lesson has
 * a better answer, an early reveal recorded, unsent marks kept through a reload or a failed send, and
 * results that say in words (not only colour) how each reason compares with the explanation.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ComparisonAttempt, ComparisonLesson } from "@/api/types";

import { user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const ID = "cmp-specific-evidence";
const lesson: ComparisonLesson = {
  id: ID, version: 1, title: "Specific evidence or general claims", teaching_goal: "See why what you did is more useful than what you're like.",
  question: "Tell me about a time you disagreed with a colleague.", kind: "clear",
  rubric: [{ id: "situation", label: "A real, specific situation" }, { id: "action", label: "What you did, step by step" }],
  samples: [
    { id: "A", label: "Answer A", sentences: [{ id: "a1", text: "I'm a strong communicator." }, { id: "a2", text: "We found a solution together." }] },
    { id: "B", label: "Answer B", sentences: [{ id: "b1", text: "A colleague wanted to launch a tool to all drivers at once." }, { id: "b2", text: "I asked for 20 minutes and brought three examples." }] },
  ],
  next_step: { to: "/drills", label: "Try a communication drill" }, review_status: "Fictional samples, written for practice.",
};
const explanation = {
  summary: "Answer B lets an interviewer see what the speaker did.", preferred: "B", alternatives: "A shorter answer with the same steps works too.",
  samples: {
    A: { strengths: [], gaps: [{ sentences: ["a1"], criterion: "situation", why: "A claim about yourself isn't evidence." }], uncertain: "We don't know what the disagreement was." },
    B: { strengths: [{ sentences: ["b2"], criterion: "action", why: "It names the steps." }], gaps: [], uncertain: "How the colleague felt isn't said." },
  },
};
const tradeoff: ComparisonLesson = {
  ...lesson, id: "cmp-tradeoffs", title: "Two good ways to handle an angry customer", kind: "tradeoff",
  question: "A customer is angry about a late order. What do you do?",
};

type Sent = { selections: { sample: string; sentence: string; kind: string; reason: string }[]; choice: string | null; revealed_early: boolean };
let sends: Sent[] = [];
let failNext = false;
function attemptFor(body: Sent, over: Partial<ComparisonAttempt> = {}): ComparisonAttempt {
  return {
    id: `cmp-att-${sends.length}`, lesson_id: ID, lesson_version: 1, current_version: 1, title: lesson.title, question: lesson.question,
    samples: lesson.samples, rubric: lesson.rubric, selections: body.selections, choice: body.choice, revealed_early: body.revealed_early,
    explanation, created_at: "2026-11-09T10:00:00Z",
    feedback: {
      rules_version: 1, method: "Fixed rules, not AI: your marks are compared with the authored explanation.",
      choice_note: body.choice === "B" ? "You chose Answer B, as the explanation does. Check that your reasons match its reasons, not just its choice." : "You didn't choose.",
      selections: body.selections.map((s) => ({
        ...s, quote: lesson.samples.find((x) => x.id === s.sample)?.sentences.find((x) => x.id === s.sentence)?.text ?? "",
        status: s.sentence === "b2" ? "matches" : "differs",
        note: s.sentence === "b2" ? "The explanation also counts this as a strength: What you did, step by step." : "The explanation reads this differently; both can have a point.",
        explanation_why: s.sentence === "b2" ? "It names the steps." : "A claim about yourself isn't evidence.",
      })),
    },
    ...over,
  };
}
function serve() {
  sends = [];
  failNext = false;
  server.use(
    http.get(`${API}/api/v1/comparisons`, () => HttpResponse.json([lesson, tradeoff].map(({ id, title, teaching_goal }) => ({ id, title, teaching_goal })))),
    http.get(`${API}/api/v1/comparisons/${ID}`, () => HttpResponse.json(lesson)),
    http.get(`${API}/api/v1/comparisons/cmp-tradeoffs`, () => HttpResponse.json(tradeoff)),
    http.get(`${API}/api/v1/comparisons/:id/explanation`, () => HttpResponse.json(explanation)),
    http.get(`${API}/api/v1/me/comparisons/:id/attempts`, () => HttpResponse.json([])),
    http.post(`${API}/api/v1/me/comparisons/:id/attempts`, async ({ request }) => {
      if (failNext) { failNext = false; return HttpResponse.json({ error: { code: "internal_error", message: "Something went wrong." } }, { status: 500 }); }
      const body = (await request.json()) as Sent;
      sends.push(body);
      return HttpResponse.json(attemptFor(body), { status: 201 });
    }),
  );
}

describe("compare sample answers", () => {
  it("lists lessons and opens one with neutral labels and no explanation until it's asked for", async () => {
    serve();
    const { user } = renderApp("/compare", { signedIn: true });
    await user.click(await screen.findByRole("link", { name: lesson.title }));
    expect(await screen.findByRole("heading", { level: 1, name: lesson.title })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Answer A/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /^Answer B/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(explanation.summary)).not.toBeInTheDocument();
    expect(screen.queryByText(/better|worse|weak|strong answer/i)).not.toBeInTheDocument();
  });

  it("marks excerpts from the keyboard, asks for reasons, and explains the comparison in words", async () => {
    serve();
    const { user } = renderApp(`/compare/${ID}`, { signedIn: true });
    // One sample at a time on a narrow screen; opening B keeps A's marks and says so.
    const strengthA = await screen.findAllByRole("button", { name: "Gap" });
    strengthA[0]!.focus();
    await user.keyboard("{Enter}");
    expect(strengthA[0]).toHaveAttribute("aria-pressed", "true");
    await user.type(screen.getByLabelText("Why is it a gap?"), "A claim about yourself proves nothing.");
    await user.click(screen.getByRole("button", { name: /^Answer B/ }));
    expect(screen.getByRole("button", { name: /^Answer A\s*· 1 marked$/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("I'm a strong communicator.")).not.toBeVisible();
    const sampleB = screen.getByRole("list", { name: "Answer B, sentence by sentence" });
    const b2 = within(sampleB).getAllByRole("listitem")[1]!;
    within(b2).getByRole("button", { name: "Strength" }).focus();
    await user.keyboard(" ");
    await user.type(within(b2).getByLabelText("Why is it a strength?"), "ok");
    await user.click(screen.getByRole("radio", { name: "Answer B" }));
    await user.click(screen.getByRole("button", { name: "Compare with the explanation" }));
    expect(screen.getByRole("status")).toHaveTextContent("Each marked excerpt needs a reason (a few words).");
    expect(sends).toHaveLength(0);
    await user.type(within(b2).getByLabelText("Why is it a strength?"), " it names exact steps");
    await user.click(screen.getByRole("button", { name: "Compare with the explanation" }));
    const result = await screen.findByRole("heading", { name: "Your reading and the explanation" });
    await waitFor(() => expect(result).toHaveFocus());
    expect(sends).toEqual([{
      selections: [
        { sample: "A", sentence: "a1", kind: "gap", reason: "A claim about yourself proves nothing." },
        { sample: "B", sentence: "b2", kind: "strength", reason: "ok it names exact steps" },
      ],
      choice: "B", revealed_early: false,
    }]);
    const results = within(screen.getByRole("list", { name: "Your marks compared with the explanation" }));
    expect(results.getByText("Matches the explanation")).toBeInTheDocument(); // words, not only colour
    expect(results.getByText("The explanation reads it differently")).toBeInTheDocument();
    expect(results.getAllByText("I asked for 20 minutes and brought three examples.").length).toBeGreaterThan(0);
    expect(screen.getByText(/Check that your reasons match its reasons/)).toBeInTheDocument();
    const shown = screen.getByRole("region", { name: "The explanation" });
    expect(shown).toHaveTextContent("Strength · What you did, step by step:");
    expect(shown).toHaveTextContent("Not settled: How the colleague felt isn't said.");
    expect(within(shown).getByRole("link", { name: "Try a communication drill" })).toHaveAttribute("href", "/drills");
    expect(localStorage.getItem(`compare-draft:${baseUser.id}:${ID}:v1`)).toBeNull();
  });

  it("an early reveal needs a confirmation and the reading records it", async () => {
    serve();
    const { user } = renderApp(`/compare/${ID}`, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Show the explanation now" }));
    await user.click(within(screen.getByRole("group", { name: "Show the explanation now?" })).getByRole("button", { name: "Not yet" }));
    expect(screen.queryByRole("region", { name: "The explanation" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show the explanation now" }));
    await user.click(screen.getByRole("button", { name: "Show the explanation" }));
    expect(await screen.findByRole("region", { name: "The explanation" })).toHaveTextContent(explanation.summary);
    await user.click(screen.getAllByRole("button", { name: "Strength" })[0]!);
    await user.type(screen.getByLabelText("Why is it a strength?"), "it sounds confident enough");
    await user.click(screen.getByRole("button", { name: "Compare with the explanation" }));
    await screen.findByRole("heading", { name: "Your reading and the explanation" });
    expect(sends[0]!.revealed_early).toBe(true);
  });

  it("unsent marks survive a reload and a failed send, and reasons are shown as text", async () => {
    serve();
    const first = renderApp(`/compare/${ID}`, { signedIn: true });
    const hostile = '<img src=x onerror="window.__cmpPwned=1"> still a reason';
    await first.user.click((await screen.findAllByRole("button", { name: "Strength" }))[1]!);
    await first.user.type(screen.getByLabelText("Why is it a strength?"), hostile);
    expect(localStorage.getItem(`compare-draft:${baseUser.id}:${ID}:v1`)).toContain("still a reason");
    first.unmount();

    serve();
    failNext = true;
    const second = renderApp(`/compare/${ID}`, { signedIn: true });
    expect(await screen.findByText("Your unsent marks were restored from this device.")).toBeInTheDocument();
    expect(screen.getByLabelText("Why is it a strength?")).toHaveValue(hostile);
    await second.user.click(screen.getByRole("button", { name: "Compare with the explanation" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByLabelText("Why is it a strength?")).toHaveValue(hostile); // kept after the failure
    await second.user.click(screen.getByRole("button", { name: "Compare with the explanation" }));
    await screen.findByRole("heading", { name: "Your reading and the explanation" });
    expect(screen.getByText(hostile)).toBeInTheDocument();
    expect(document.querySelector("img[src='x']")).toBeNull();
    expect((window as { __cmpPwned?: number }).__cmpPwned).toBeUndefined();
  });

  it("a tradeoff lesson asks for no choice", async () => {
    serve();
    const { user } = renderApp("/compare/cmp-tradeoffs", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "No single best answer" })).toBeInTheDocument();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Strength" })[0]!);
    await user.type(screen.getByLabelText("Why is it a strength?"), "lets the customer speak first");
    await user.click(screen.getByRole("button", { name: "Compare with the explanation" }));
    await waitFor(() => expect(sends).toHaveLength(1));
    expect(sends[0]!.choice).toBeNull();
  });
});
