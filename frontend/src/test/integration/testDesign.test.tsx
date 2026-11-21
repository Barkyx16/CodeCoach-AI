/**
 * Test design (Volume 10, prompt 4; docs/TEST_DESIGN.md): cases are written in plain fields with
 * plain errors, kept on this device until run, sent once, and the report shows what the sandbox's
 * outputs showed: which faulty versions each case told apart, a case that disagrees with the
 * specification counting against nothing, coverage worded as these versions only. Without a judge
 * the cases are saved and said not to have run.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { TestDesignExercise, TestDesignReport, TestDesignRun } from "@/api/types";
import { draftKey } from "@/features/testDesign/cases";

import { user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const SLUG = "tests-count-in-range";
const exercise = (enabled = true): TestDesignExercise => ({
  slug: SLUG, version: 1, title: "Test design: Count in Range", summary: "Count the values between two bounds.",
  spec: "`countInRange(nums, lo, hi)` counts values **at least lo and at most hi**.", method: "countInRange",
  params: [{ name: "nums", type: "int[]" }, { name: "lo", type: "int" }, { name: "hi", type: "int" }], returns: "int",
  limits: { max_cases: 12, max_length: 20, min_value: -1000, max_value: 1000 },
  examples: [{ input: { nums: [1, 5, 9], lo: 2, hi: 8 }, expected: 1 }], variant_count: 4,
  review_status: "Machine-checked.", execution_enabled: enabled,
});
const report: TestDesignReport = {
  report_version: 1, caught: 2, total: 4, gap: { variant: "B", hint: "Try a value that equals lo exactly." },
  summary: [
    "Your cases tell 2 of the 4 authored faulty versions apart from the reference.",
    "This counts only the 4 faulty versions written for this exercise. It says nothing about every possible defect, or about any hidden tests in the problem bank.",
    "1 case had an expected output that disagrees with the specification, so they weren't counted.",
  ],
  cases: [
    { case: 1, label: "boundary", label_text: "Boundary", reference_output: "2", status: "counted", distinguishes: ["A", "C"], new: ["A", "C"], notes: ["Tells apart 2 faulty versions that no earlier case did."] },
    { case: 2, label: null, reference_output: "1", status: "disagrees", distinguishes: [], new: [], notes: ["The specification's reference returns 1 here, not 3."] },
  ],
  variants: [
    { key: "A", caught_by: [1], title: "Leaves out values equal to hi" },
    { key: "B", caught_by: [], title: null },
    { key: "C", caught_by: [1], title: "Never looks at the last value" },
    { key: "D", caught_by: [], title: null },
  ],
};
const sentCases = [
  { input: { nums: [3, 7], lo: 1, hi: 7 }, expected: 2, label: "boundary", note: "hi itself" },
  { input: { nums: [1, 5, 9], lo: 2, hi: 8 }, expected: 3, label: null, note: "" },
];
const run = (over: Partial<TestDesignRun>): TestDesignRun => ({
  id: "run-1", slug: SLUG, exercise_version: 1, current_version: 1, status: "done", status_detail: "Ran.",
  cases: sentCases, report: report as unknown as TestDesignRun["report"], created_at: "2026-11-09T10:00:00Z", judged_at: "2026-11-09T10:00:02Z", ...over,
});

let posted: unknown[] = [];
let variantCalls = 0;
function serve({ enabled = true, first = run({ status: "queued", report: null }), later = run({}) } = {}) {
  posted = [];
  variantCalls = 0;
  let polls = 0;
  server.use(
    http.get(`${API}/api/v1/test-design`, () => HttpResponse.json([{ slug: SLUG, title: "Test design: Count in Range", summary: "Count the values between two bounds.", variant_count: 4 }])),
    http.get(`${API}/api/v1/test-design/${SLUG}`, () => HttpResponse.json(exercise(enabled))),
    // Shown to you and recorded first (Volume 19, prompt 3): the page asks the recording route.
    http.post(`${API}/api/v1/me/test-design/${SLUG}/variants`, () => {
      variantCalls += 1;
      return HttpResponse.json({ recorded_at: "2026-11-18T09:00:00Z", variants: [{ key: "A", title: "Leaves out values equal to hi", defect: "v < hi" }, { key: "B", title: "Leaves out values equal to lo", defect: "v > lo" }] });
    }),
    http.post(`${API}/api/v1/me/test-design/${SLUG}/runs`, async ({ request }) => { posted.push(await request.json()); return HttpResponse.json(first, { status: 202 }); }),
    http.get(`${API}/api/v1/me/test-design/runs/:id`, () => { polls += 1; return HttpResponse.json(polls > 1 ? later : first); }),
    http.get(`${API}/api/v1/me/test-design/${SLUG}/runs`, () => HttpResponse.json(posted.length ? [{ id: "run-1", exercise_version: 1, status: "done", cases: 2, caught: 2, total: 4, outcome_text: "2 cases · told apart 2 of 4 faulty versions · version 1", created_at: "2026-11-09T10:00:00Z" }] : [])),
  );
}

async function fillCase(user: ReturnType<typeof renderApp>["user"], index: number, nums: string, lo: string, hi: string, expected: string) {
  await user.type((await screen.findAllByLabelText(/^nums/))[index]!, nums);
  await user.type(screen.getAllByLabelText(/^lo/)[index]!, lo);
  if (hi) await user.type(screen.getAllByLabelText(/^hi/)[index]!, hi);
  await user.type(screen.getAllByLabelText("Expected output")[index]!, expected);
}

describe("test design", () => {
  it("is reached from the coding library; the specification shows, the faulty versions don't", async () => {
    serve();
    const { user } = renderApp("/problems", { signedIn: true });
    await user.click(await screen.findByRole("link", { name: "Test design: write cases that find bugs" }));
    await user.click(await screen.findByRole("link", { name: "Test design: Count in Range" }));
    expect(await screen.findByText("int countInRange(int[] nums, int lo, int hi)")).toBeInTheDocument();
    expect(screen.getByText(/4 faulty versions written for this exercise/)).toBeInTheDocument();
    expect(screen.queryByText(/Leaves out values/)).not.toBeInTheDocument();
  });

  it("malformed fields get plain messages and nothing is sent", async () => {
    serve();
    const { user } = renderApp(`/test-design/${SLUG}`, { signedIn: true });
    await fillCase(user, 0, "3, x", "1", "", "2");
    await user.click(screen.getByRole("button", { name: "Run my cases" }));
    expect(screen.getByText("Whole numbers separated by commas, like 3, -1, 7.")).toBeInTheDocument();
    expect(screen.getByText("Give a value.")).toBeInTheDocument();
    expect(screen.getAllByLabelText(/^nums/)[0]).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Some cases need fixing first; the messages are next to the fields.")).toBeInTheDocument();
    expect(posted).toEqual([]);
  });

  it("runs the cases once and reports what the sandbox showed, by letter, with the coverage caveat", async () => {
    serve();
    const { user } = renderApp(`/test-design/${SLUG}`, { signedIn: true });
    await fillCase(user, 0, "3, 7", "1", "7", "2");
    await user.selectOptions(screen.getByLabelText("What kind of case (optional)"), "boundary");
    await user.click(screen.getByRole("button", { name: "Add a case" }));
    expect(screen.getAllByLabelText(/^nums/)[1]).toHaveFocus();
    await fillCase(user, 1, "1, 5, 9", "2", "8", "3");
    await user.click(screen.getByRole("button", { name: "Run my cases" }));
    expect(posted).toEqual([{ cases: [
      { input: { nums: [3, 7], lo: 1, hi: 7 }, expected: 2, label: "boundary", note: "" },
      { input: { nums: [1, 5, 9], lo: 2, hi: 8 }, expected: 3, label: null, note: "" },
    ], client_request_id: expect.any(String) }]);
    const shows = await screen.findByRole("region", { name: "What your cases show" }, { timeout: 4000 });
    expect(shows).toHaveTextContent("Your cases tell 2 of the 4 authored faulty versions apart from the reference.");
    expect(shows).toHaveTextContent("This counts only the 4 faulty versions written for this exercise.");
    const byCase = screen.getByRole("region", { name: "Case by case" });
    expect(byCase).toHaveTextContent("Tells apart versions A, C.");
    expect(within(byCase).getByText("Disagrees with the specification")).toBeInTheDocument();
    const versions = screen.getByRole("region", { name: "The faulty versions" });
    expect(versions).toHaveTextContent("Version A: Leaves out values equal to hi. Told apart by case 1.");
    expect(versions).toHaveTextContent("Version B: not told apart by these cases.");
    expect(versions).not.toHaveTextContent("equal to lo");
    expect(within(versions).getByRole("note")).toHaveTextContent("One gap to investigate (version B)");
  });

  it("without a judge the cases are saved and said not to have run; nothing is shown as a result", async () => {
    serve({ enabled: false, first: run({ status: "not_run", report: null, status_detail: "Code can't run on this server, so these cases weren't run. They're saved with this exercise version; nothing was guessed." }) });
    const { user } = renderApp(`/test-design/${SLUG}`, { signedIn: true });
    expect(await screen.findByRole("note")).toHaveTextContent("Code can't run on this server.");
    await fillCase(user, 0, "3, 7", "1", "7", "2");
    await user.click(screen.getByRole("button", { name: "Save my cases (not run)" }));
    const result = await screen.findByRole("heading", { name: "Report" });
    expect(result.parentElement).toHaveTextContent("these cases weren't run");
    expect(screen.queryByRole("region", { name: "What your cases show" })).not.toBeInTheDocument();
  });

  it("unsent cases stay on this device through a reload; an earlier run's cases can be edited as a new attempt", async () => {
    serve();
    const first = renderApp(`/test-design/${SLUG}`, { signedIn: true });
    await fillCase(first.user, 0, "0, 4", "3", "5", "1");
    expect(localStorage.getItem(draftKey(baseUser.id, SLUG))).toContain("0, 4");
    first.unmount();
    serve();
    const second = renderApp(`/test-design/${SLUG}`, { signedIn: true });
    expect(await screen.findByText("Your unsent cases were restored from this device.")).toBeInTheDocument();
    expect(screen.getAllByLabelText(/^nums/)[0]).toHaveValue("0, 4");
    await second.user.click(screen.getByRole("button", { name: "Run my cases" }));
    await second.user.click(await screen.findByRole("button", { name: "Edit these cases" }));
    await waitFor(() => expect(screen.getAllByLabelText(/^nums/)).toHaveLength(2));
    expect(screen.getAllByLabelText(/^nums/)[0]).toHaveValue("3, 7");
    expect(screen.getAllByLabelText("What it covers (optional)")[0]).toHaveValue("hi itself");
  });

  it("an earlier run is listed in the server's words, the ones History uses", async () => {
    serve();
    const { user } = renderApp(`/test-design/${SLUG}`, { signedIn: true });
    await fillCase(user, 0, "3, 7", "1", "7", "2");
    await user.click(screen.getByRole("button", { name: "Run my cases" }));
    const earlier = await screen.findByRole("region", { name: "Your earlier runs" });
    expect(earlier).toHaveTextContent("2 cases · told apart 2 of 4 faulty versions · version 1");
  });

  it("a History link opens that run's report and moves focus to it", async () => {
    serve({ first: run({}) });
    renderApp(`/test-design/${SLUG}?attempt=run-1`, { signedIn: true });
    const heading = await screen.findByRole("heading", { name: "Report" });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.getByText(/Your cases tell 2 of the 4 authored faulty versions apart/)).toBeInTheDocument();
  });

  it("a link to a run that isn't this exercise's, or isn't yours, says it couldn't be opened", async () => {
    serve({ first: run({ slug: "tests-longest-run" }) });
    const one = renderApp(`/test-design/${SLUG}?attempt=run-1`, { signedIn: true });
    expect(await screen.findByText(/That attempt couldn't be opened/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Report" })).toBeNull();
    one.unmount();
    serve();
    server.use(http.get(`${API}/api/v1/me/test-design/runs/:id`, () => HttpResponse.json({ error: { code: "not_found", message: "Run not found", request_id: "r", details: null } }, { status: 404 })));
    renderApp(`/test-design/${SLUG}?attempt=run-9`, { signedIn: true });
    expect(await screen.findByText(/That attempt couldn't be opened/)).toBeInTheDocument();
  });

  it("the faulty versions are shown only after a confirmed ask", async () => {
    serve();
    const { user } = renderApp(`/test-design/${SLUG}`, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Stuck? Show what the faulty versions get wrong" }));
    await user.click(screen.getByRole("button", { name: "Not yet" }));
    expect(variantCalls).toBe(0);
    await user.click(screen.getByRole("button", { name: "Stuck? Show what the faulty versions get wrong" }));
    await user.click(screen.getByRole("button", { name: "Show the faulty versions" }));
    expect(await screen.findByText(/Version B: Leaves out values equal to lo\./)).toBeInTheDocument();
    expect(variantCalls).toBe(1);
  });

  it("signed out the exercise asks you to sign in, and no page reads the public route (Volume 20, prompt 4)", async () => {
    serve();
    let publicCalls = 0;
    server.use(http.get(`${API}/api/v1/test-design/:slug/variants`, () => {
      publicCalls += 1;
      return HttpResponse.json({ error: { code: "faulty_versions_need_sign_in", message: "Sign in." } }, { status: 410 });
    }));
    const out = renderApp(`/test-design/${SLUG}`);
    // The sign-in page, which brings you back to the exercise afterwards.
    expect(await screen.findByRole("heading", { level: 1, name: "Welcome back" })).toBeInTheDocument();
    expect(out.router.state.location.pathname).toBe("/login");
    expect(screen.queryByRole("button", { name: /Show the faulty versions/ })).not.toBeInTheDocument();
    out.unmount();
    // Signed in, only the recorded showing is asked.
    const { user } = renderApp(`/test-design/${SLUG}`, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Stuck? Show what the faulty versions get wrong" }));
    await user.click(screen.getByRole("button", { name: "Show the faulty versions" }));
    expect(await screen.findByText(/Version B: Leaves out values equal to lo\./)).toBeInTheDocument();
    expect([variantCalls, publicCalls]).toEqual([1, 0]);
  });

  it("a run's report and its row in the list say what help came before it (Volume 19, prompt 3)", async () => {
    const revealed = {
      labels: ["Solution revealed"], help: [{ label: "Solution revealed", detail: "The faulty versions were shown before these cases were written", at: "2026-11-18T09:00:00Z" }],
      recorded_from: "2026-11-15", note: "Only help shown in CodeCoach is recorded.", round: null, interview: null, unrecorded: null,
    };
    const withHelp = run({ conditions: revealed } as Partial<TestDesignRun>);
    serve({ first: withHelp, later: withHelp });
    server.use(http.get(`${API}/api/v1/me/test-design/${SLUG}/runs`, () => HttpResponse.json([
      { id: "run-1", exercise_version: 1, status: "done", cases: 2, caught: 2, total: 4, outcome_text: "2 cases · told apart 2 of 4 faulty versions · version 1", conditions: revealed, created_at: "2026-11-18T10:00:00Z" },
    ])));
    renderApp(`/test-design/${SLUG}?attempt=run-1`, { signedIn: true });
    expect(await screen.findByText("In-app help before this run:", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText(/The faulty versions were shown before these cases were written/)).toBeInTheDocument();
    const earlier = await screen.findByRole("region", { name: "Your earlier runs" });
    expect(earlier).toHaveTextContent("In-app help: Solution revealed");
  });

  it("a run is set beside the run before it, with a link to that run's report, and the list says the same (Volume 19, prompt 4)", async () => {
    const first = run({ id: "run-1", created_at: "2026-11-18T09:00:00Z", not_compared: "Not compared: the first judged run of this exercise" } as Partial<TestDesignRun>);
    const explanation = "Partly comparable: the in-app help differed: before the earlier one, none recorded; before the later one, solution revealed. The counts are of the same authored faulty versions, so both are shown. Both counts are of the faulty versions written for this exercise only, not of every possible defect. (Comparison rules v1)";
    const compared = {
      previous: { id: "run-1", created_at: "2026-11-18T09:00:00Z", result: "told apart 1 of 4 faulty versions" },
      result: "told apart 2 of 4 faulty versions",
      comparison: { against: "run-1", outcome: "partially_comparable" as const, scores_comparable: true, points_comparable: true, reasons: [{ rule: "help", kind: "partial_conditions" as const, text: "the in-app help differed" }], explanation, contract_version: 1 },
    };
    const second = run({ id: "run-2", created_at: "2026-11-18T10:00:00Z", compared } as Partial<TestDesignRun>);
    serve();
    server.use(
      http.get(`${API}/api/v1/me/test-design/runs/:id`, ({ params }) => HttpResponse.json(params.id === "run-1" ? first : second)),
      http.get(`${API}/api/v1/me/test-design/${SLUG}/runs`, () => HttpResponse.json([
        { id: "run-2", exercise_version: 1, status: "done", cases: 2, caught: 2, total: 4, outcome_text: "2 cases · told apart 2 of 4 faulty versions · version 1", compared, not_compared: null, created_at: "2026-11-18T10:00:00Z" },
        { id: "run-1", exercise_version: 1, status: "done", cases: 2, caught: 1, total: 4, outcome_text: "2 cases · told apart 1 of 4 faulty versions · version 1", compared: null, not_compared: "Not compared: the first judged run of this exercise", created_at: "2026-11-18T09:00:00Z" },
      ])),
    );
    const { user } = renderApp(`/test-design/${SLUG}?attempt=run-2`, { signedIn: true });
    const beside = await screen.findByRole("region", { name: "Compared with your previous attempt" }, { timeout: 3000 });
    expect(beside).toHaveTextContent("told apart 1 of 4 faulty versions");
    expect(beside).toHaveTextContent("This one: told apart 2 of 4 faulty versions");
    expect(beside).toHaveTextContent(explanation);
    expect(beside).not.toHaveTextContent(/improv|better/i);
    // The earlier run is named by its time; the list's rows say the contract's short words, as History does.
    expect(within(beside).getByText(/^Earlier,/).querySelector("time")).toHaveAttribute("dateTime", "2026-11-18T09:00:00Z");
    const earlier = await screen.findByRole("region", { name: "Your earlier runs" });
    const rows = within(earlier).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("2 cases · told apart 2 of 4 faulty versions · version 1 · Partly comparable with the one before");
    expect(rows[1]).toHaveTextContent("· Not compared: the first judged run of this exercise");
    // Its link opens the earlier run's report.
    const link = within(beside).getByRole("link", { name: "Open that run's report" });
    expect(link).toHaveAttribute("href", `/test-design/${SLUG}?attempt=run-1`);
    await user.click(link);
    expect(await screen.findByText("Not compared: the first judged run of this exercise.", { selector: "p" }, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Compared with your previous attempt" })).not.toBeInTheDocument();
  });

  it("the server's per-case messages are shown next to the case", async () => {
    serve();
    server.use(http.post(`${API}/api/v1/me/test-design/${SLUG}/runs`, () => HttpResponse.json(
      { error: { code: "invalid_cases", message: "Case 1: nums: each value between -1000 and 1000.", details: { cases: { "1": ["nums: each value between -1000 and 1000."] } } } },
      { status: 422 },
    )));
    const { user } = renderApp(`/test-design/${SLUG}`, { signedIn: true });
    await fillCase(user, 0, "3", "1", "7", "1");
    await user.click(screen.getByRole("button", { name: "Run my cases" }));
    // Beside the case it belongs to, as well as in the summary under the button.
    const beside = await screen.findByText("nums: each value between -1000 and 1000.", { selector: "p.field__error" });
    expect(beside.closest("fieldset")).toHaveTextContent("Case 1");
  });
});
