/**
 * Code-review practice (Volume 10, prompt 3; docs/CODE_REVIEW_PRACTICE.md): the learner reviews
 * someone else's code. The role is said up front; findings cite lines and show the cited code;
 * drafts survive a reload; the authored review waits until asked or a review is sent; the
 * comparison names where findings point (never a score) and labels preferences; code and learner
 * text render as text; an old review keeps the version it reviewed.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ReviewAttempt, ReviewDraft, ReviewExercise, ReviewReference } from "@/api/types";

import { user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const code = [
  "class Solution {",
  "    /** Returns the largest value in nums. <img src=x onerror=\"window.__pwned=1\"> */",
  "    public int max(int[] nums) {",
  "        if (nums.length == 0) {",
  "            throw new IllegalArgumentException(\"nums is empty\");",
  "        }",
  "        int largest = 0;",
  "        for (int i = 0; i < nums.length; i++) {",
  "            if (nums[i] > largest) {",
  "                largest = nums[i];",
  "            }",
  "        }",
  "        return largest;",
  "    }",
  "}",
  "",
].join("\n");

const exercise: ReviewExercise = {
  slug: "review-largest-number", version: 1, title: "Review: Largest Number",
  context: "A teammate wrote this and asked you to review it before it's merged.",
  code, line_count: 15, problem_slug: "find-largest-number", problem_title: "Find Largest Number", difficulty: "easy",
  statement: "Return the largest value.", constraints: ["0 <= nums.length <= 10^5"],
  public_tests: [
    { position: 1, input: { nums: [3, 7, 2, 9, 4] }, expected_output: 9 },
    { position: 2, input: { nums: [-5, -2, -11] }, expected_output: -2 },
  ],
  review_status: "Written for practice and machine-checked.",
};
const reference: ReviewReference = {
  version: 1, debrief: "One real defect, shown by a public test.", repaired_code: code.replace("int largest = 0;", "int largest = nums[0];"),
  findings: [
    { id: "starts-at-zero", kind: "defect", lines: [7, 7], related_lines: [[9, 10]], excerpt: "        int largest = 0;", title: "The running maximum starts at 0",
      explanation: "A value only replaces it if it is above 0.", consequence: "All-negative arrays get 0.", repair: "Start from nums[0].", why_preference: null,
      evidence: [{ public_test: 2, input: { nums: [-5, -2, -11] }, expected: -2, actual: 0 }] },
    { id: "index-loop", kind: "observation", lines: [8, 8], related_lines: [], excerpt: "        for (int i = 0; i < nums.length; i++) {", title: "An index loop where only the values are used",
      explanation: "for (int n : nums) would say it more directly.", consequence: "None for correctness.", repair: "Optional.", why_preference: "No test can tell them apart.", evidence: [] },
  ],
};
const emptyDraft: ReviewDraft = {
  slug: exercise.slug, exercise_version: 1, current_version: 1, findings: [], summary: "", revision: 0, revealed: false, updated_at: null,
};
const hostile = "<script>window.__pwned=2</script> starts at <b>zero</b>";
const sent: ReviewAttempt = {
  id: "rev-1", slug: exercise.slug, exercise_version: 1, current_version: 1, title: exercise.title, problem_title: exercise.problem_title, code,
  findings: [
    { id: "a", start_line: 7, end_line: 7, excerpt: "        int largest = 0;", problem: hostile, consequence: "negative arrays return 0", repair: "use nums[0]", anchor: "same" },
    { id: "b", start_line: 4, end_line: 6, excerpt: "...", problem: "the empty check is wrong", consequence: "", repair: "", anchor: "same" },
  ],
  summary: "", reference, after_reveal: false, created_at: "2026-11-09T10:00:00Z",
  feedback: {
    rubric_version: 1, defects_total: 1, defects_raised: 1, unsupported: 1, method: "Fixed rules, not AI: where each finding points.",
    summary: ["The authored review has one defect, shown by a public test. Your review points at it."],
    findings: [
      { id: "a", location: "defect", matches: ["starts-at-zero"], consequence: true, repair: true, notes: ["Points at the same code as the authored defect.", "Says what happens because of it.", "Suggests a next step."] },
      { id: "b", location: "unsupported", matches: [], consequence: false, repair: false, notes: ["No authored finding covers lines 4–6.", "Add what happens because of it: which input goes wrong, and how.", "Add a next step: a change, or a test that would show the problem."] },
    ],
    reference: [{ id: "starts-at-zero", raised_by: ["a"] }, { id: "index-loop", raised_by: [] }],
  },
};

let calls: { reveal: number; saves: unknown[]; sends: unknown[] };
function serve(draft: ReviewDraft = emptyDraft, attempt: ReviewAttempt = sent) {
  calls = { reveal: 0, saves: [], sends: [] };
  let current = draft;
  server.use(
    http.get(`${API}/api/v1/code-reviews`, () => HttpResponse.json([{ slug: exercise.slug, title: exercise.title, difficulty: "easy", problem_slug: "find-largest-number", problem_title: "Find Largest Number" }])),
    http.get(`${API}/api/v1/code-reviews/${exercise.slug}`, () => HttpResponse.json(exercise)),
    http.get(`${API}/api/v1/me/code-reviews/${exercise.slug}/draft`, () => HttpResponse.json(current)),
    http.put(`${API}/api/v1/me/code-reviews/${exercise.slug}/draft`, async ({ request }) => {
      const body = (await request.json()) as { findings: ReviewDraft["findings"]; summary: string; expected_revision: number };
      calls.saves.push(body);
      if (body.expected_revision !== current.revision) {
        return HttpResponse.json({ error: { code: "stale_revision", message: "This review was saved somewhere else.", details: { current_revision: current.revision, current } } }, { status: 409 });
      }
      current = { ...current, findings: body.findings.map((f) => ({ ...f, excerpt: "", anchor: "same" as const })), summary: body.summary, revision: current.revision + 1, updated_at: "2026-11-09T10:00:00Z" };
      return HttpResponse.json(current);
    }),
    http.post(`${API}/api/v1/me/code-reviews/${exercise.slug}/reveal`, () => { calls.reveal += 1; return HttpResponse.json(reference); }),
    http.post(`${API}/api/v1/me/code-reviews/${exercise.slug}/attempts`, async ({ request }) => { calls.sends.push(await request.json()); return HttpResponse.json(attempt, { status: 201 }); }),
    http.get(`${API}/api/v1/me/code-reviews/${exercise.slug}/attempts`, () => HttpResponse.json([])),
    http.get(`${API}/api/v1/me/code-reviews/attempts/:id`, () => HttpResponse.json(attempt)),
  );
}

describe("code-review practice", () => {
  it("is reached from the coding library and says whose code it is", async () => {
    serve();
    const { user } = renderApp("/problems", { signedIn: true });
    await user.click(await screen.findByRole("link", { name: "Code review: review someone else's code" }));
    expect(await screen.findByRole("heading", { name: "Review someone else's code", level: 1 })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Review: Largest Number" }));
    expect(await screen.findByText("CODE REVIEW · YOU'RE THE REVIEWER")).toBeInTheDocument();
    expect(screen.getByText(/Someone else wrote this code/)).toHaveTextContent("This isn't the coach reviewing your code");
    expect(screen.getByRole("region", { name: /The task/ })).toHaveTextContent("nums = [-5, -2, -11] should give -2");
    expect(screen.queryByText("The running maximum starts at 0")).not.toBeInTheDocument(); // the reference waits
  });

  it("a finding cites lines by keyboard, shows the cited code, and refuses lines outside it; no severity is asked", async () => {
    serve();
    const { user } = renderApp(`/code-reviews/${exercise.slug}`, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Add a finding" }));
    const from = screen.getByLabelText("From line");
    expect(from).toHaveFocus(); // the new finding's first field
    await user.keyboard("7");
    expect(screen.getByLabelText("The code at line 7")).toHaveTextContent("int largest = 0;");
    expect(screen.getByText("Showing line 7 of finding 1.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("To line"), "40");
    expect(screen.getByText("The code has lines 1 to 15.")).toBeInTheDocument();
    expect(screen.getByLabelText("To line")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("button", { name: "Send review and compare" })).toBeDisabled();
    await user.clear(screen.getByLabelText("To line"));
    expect(screen.getByRole("button", { name: "Send review and compare" })).toBeEnabled();
    expect(screen.queryByLabelText(/severity/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove finding 1" }));
    expect(screen.getByRole("button", { name: "Add a finding" })).toHaveFocus();
  });

  it("an unsaved review is kept on this device and comes back after a reload; a save goes to the account", async () => {
    serve();
    const first = renderApp(`/code-reviews/${exercise.slug}`, { signedIn: true });
    await first.user.click(await screen.findByRole("button", { name: "Add a finding" }));
    await first.user.keyboard("7");
    screen.getByLabelText("What's wrong").focus();
    await first.user.keyboard("largest starts at 0");
    expect(screen.getByText("Unsaved changes, kept on this device")).toBeInTheDocument();
    expect(localStorage.getItem(`code-review-draft:${baseUser.id}:${exercise.slug}`)).toContain("largest starts at 0");
    first.unmount();

    serve();
    const second = renderApp(`/code-reviews/${exercise.slug}`, { signedIn: true });
    const banner = await screen.findByRole("region", { name: "Unsaved changes" });
    await second.user.click(within(banner).getByRole("button", { name: "Restore them" }));
    expect(screen.getByLabelText("What's wrong")).toHaveValue("largest starts at 0");
    await second.user.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("Saved to your account.")).toBeInTheDocument();
    expect(calls.saves).toEqual([expect.objectContaining({ expected_revision: 0, findings: [expect.objectContaining({ start_line: 7, end_line: 7, problem: "largest starts at 0" })] })]);
    expect(localStorage.getItem(`code-review-draft:${baseUser.id}:${exercise.slug}`)).toBeNull();
  });

  it("a save refused because another tab saved first shows both versions; nothing is overwritten", async () => {
    serve({ ...emptyDraft, revision: 3, summary: "from the other tab" });
    const { user } = renderApp(`/code-reviews/${exercise.slug}`, { signedIn: true });
    await screen.findByRole("button", { name: "Add a finding" });
    serve({ ...emptyDraft, revision: 4, summary: "newer, from the other tab" });
    await user.type(screen.getByLabelText(/^Summary \(optional\)/), " and mine");
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    const conflict = await screen.findByRole("region", { name: "Edit conflict" });
    expect(conflict).toHaveTextContent("newer, from the other tab");
    expect(screen.getByLabelText(/^Summary \(optional\)/)).toHaveValue("from the other tab and mine");
  });

  it("the authored review waits until asked; stepping back fetches nothing", async () => {
    serve();
    const { user } = renderApp(`/code-reviews/${exercise.slug}`, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Stuck? Show the authored review" }));
    await user.click(screen.getByRole("button", { name: "Not yet" }));
    expect(calls.reveal).toBe(0);
    await user.click(screen.getByRole("button", { name: "Stuck? Show the authored review" }));
    await user.click(screen.getByRole("button", { name: "Show the authored review" }));
    const heading = await screen.findByRole("heading", { name: "The authored review", level: 2 });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(calls.reveal).toBe(1);
    const shown = screen.getByRole("region", { name: "What the author of this exercise found" });
    expect(shown).toHaveTextContent("Defect · shown by a public test");
    expect(shown).toHaveTextContent("Observation · a preference, not a defect");
    expect(shown).toHaveTextContent("Public test 2: nums = [-5, -2, -11] should give -2; this code returns 0.");
    expect(shown).toHaveTextContent("Why it's a preference: No test can tell them apart.");
  });

  it("a sent review is compared by location with notes, not a score; hostile text stays text", async () => {
    serve();
    const { user } = renderApp(`/code-reviews/${exercise.slug}`, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Add a finding" }));
    await user.keyboard("7");
    screen.getByLabelText("What's wrong").focus();
    await user.keyboard("largest starts at zero");
    await user.click(screen.getByRole("button", { name: "Send review and compare" }));
    const heading = await screen.findByRole("heading", { name: "Your review and the authored one" });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(calls.sends).toEqual([{ findings: [expect.objectContaining({ start_line: 7, end_line: 7, problem: "largest starts at zero" })], summary: "" }]);
    const yours = screen.getByRole("region", { name: "Your findings" });
    expect(within(yours).getByText("Points at an authored defect")).toBeInTheDocument();
    expect(within(yours).getByText("Not covered by the authored review")).toBeInTheDocument();
    expect(within(yours).getByRole("list", { name: "Notes on finding 2" })).toHaveTextContent("No authored finding covers lines 4–6.");
    expect(yours).toHaveTextContent(hostile); // shown as typed...
    expect(document.querySelector("script:not([src]), b, img[src='x']")).toBeNull(); // ...never parsed
    expect((window as { __pwned?: number }).__pwned).toBeUndefined();
    const ref = screen.getByRole("region", { name: "The authored review" });
    expect(ref).toHaveTextContent("In your review: finding 1.");
    expect(ref).toHaveTextContent("Not in your review.");
    expect(screen.getByRole("region", { name: "How your review compares" })).not.toHaveTextContent(/score|\d+%/i);
  });

  it("an old review keeps the code and the authored review it was compared with", async () => {
    serve(emptyDraft, { ...sent, current_version: 2 });
    renderApp("/code-reviews/attempts/rev-1", { signedIn: true });
    expect(await screen.findByText(/The exercise is version 2 now/)).toBeInTheDocument();
    expect(screen.getByLabelText("The code you reviewed (version 1), with line numbers")).toHaveTextContent("int largest = 0;");
    expect(screen.getByRole("region", { name: "The authored review" })).toHaveTextContent("The running maximum starts at 0");
  });

  it("a draft written against an earlier version says which findings moved and which weren't found", async () => {
    serve({
      ...emptyDraft, exercise_version: 1, current_version: 2, revision: 2,
      findings: [
        { id: "a", start_line: 7, end_line: 7, excerpt: "        int largest = 0;", problem: "starts at zero", consequence: "", repair: "", anchor: "moved" },
        { id: "b", start_line: 2, end_line: 2, excerpt: "old comment", problem: "comment", consequence: "", repair: "", anchor: "missing" },
      ],
    });
    renderApp(`/code-reviews/${exercise.slug}`, { signedIn: true });
    expect(await screen.findByRole("note")).toHaveTextContent("corrected after you started (version 1 → 2)");
    expect(screen.getByText("Moved to line 7 to follow the code you cited.")).toBeInTheDocument();
    expect(screen.getByText("The code you cited isn't in the corrected version. Check this finding's lines.")).toBeInTheDocument();
  });
});
