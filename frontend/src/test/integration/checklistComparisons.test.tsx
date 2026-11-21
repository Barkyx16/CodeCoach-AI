import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { AttemptConditions, Drill, DrillAttempt, PracticeComparison, WhiteboardAttempt, WhiteboardAttemptSummary, WhiteboardDraft, WhiteboardPromptList, WorkSampleAttempt, WorkSampleBrief, WorkSampleDraft } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

/**
 * Drills, whiteboard designs and work samples compared by the one contract (Volume 15, prompt 4;
 * docs/COMPARING_ATTEMPTS.md): each attempt's page shows both results as they were given and the
 * contract's own explanation, and its row in the attempts list says the outcome in one line.
 */
const NOTE = "Only help shown in CodeCoach is recorded.";
const none: AttemptConditions = { labels: ["No in-app help recorded"], recorded_from: "2026-11-15", note: NOTE, help: [], round: null };
const signIn = (career = "registered-nurse") =>
  server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: career } }))));

const compared = (outcome: PracticeComparison["comparison"]["outcome"], explanation: string, before: string, now: string, points = true): PracticeComparison => ({
  previous: { id: "earlier", created_at: "2026-11-15T09:05:00Z", result: before },
  result: now,
  comparison: { against: "earlier", outcome, scores_comparable: outcome === "comparable", points_comparable: points, reasons: [], explanation, contract_version: 1 },
});

const D = `${API}/api/v1/me/drills`;
const example: Drill = {
  id: "example", title: "Answer with a concrete example", objective: "One specific example.", looks_for: ["Answers the question", "One specific situation"],
  target_seconds: null, prompt: "Tell me about a time patient assessment really mattered.", attempts: 2,
};
const drillAttempt = (id: string, at: string, c: PracticeComparison | null, points: string[] | null): DrillAttempt => ({
  id, drill_id: "example", prompt: example.prompt, text: "When two patients needed me at once I saw the one short of breath first.", source: "typed",
  spoken_seconds: null, rubric_version: 1, created_at: at, compared_with_previous: points, conditions: none, compared: c,
  feedback: {
    rubric_version: 1,
    observations: [{ point: "Answers the question", present: true, detail: "It answers it" }, { point: "One specific situation", present: false, detail: "None found" }],
    generalities: [], measured: { words: 14, reading_estimate_seconds: 6 }, notes: [], limitations: "Built-in rules.",
  },
});

function serveDrill(attempts: DrillAttempt[]) {
  server.use(
    http.get(`${D}/example`, () => HttpResponse.json(example)),
    http.get(`${D}/example/attempts`, () => HttpResponse.json(attempts)),
  );
}

describe("Drills, whiteboards and work samples compared by the one contract", () => {
  it("a drill attempt shows both results and the contract's explanation; its row says the outcome in one line", async () => {
    signIn();
    const explanation = "Partly comparable: the in-app help differed: before the earlier one, hint shown; before the later one, none recorded. The results are from the same checks by the same fixed rules, so both are shown. (Comparison rules v1)";
    const second = drillAttempt("d2", "2026-11-15T09:20:00Z", compared("partially_comparable", explanation, "2 of 2 points there", "1 of 2 points there"), [
      "Not there this time: one specific situation.",
      "The in-app help differed: before the earlier one, hint shown; before this one, none recorded.",
    ]);
    serveDrill([second, drillAttempt("earlier", "2026-11-15T09:05:00Z", null, null)]);
    renderApp("/drills/example?attempt=d2", { signedIn: true });
    const fb = await screen.findByRole("region", { name: /Feedback on your attempt from/ });
    const block = within(fb).getByRole("region", { name: "Compared with your previous attempt" });
    expect(block).toHaveTextContent(/Earlier, .*: 2 of 2 points there/);
    expect(block).toHaveTextContent("This one: 1 of 2 points there");
    expect(within(block).getByText(explanation)).toBeInTheDocument();
    // Point by point, without repeating the help the explanation already names.
    expect(within(fb).getByRole("heading", { name: "Point by point" })).toBeInTheDocument();
    expect(within(fb).getByText("Not there this time: one specific situation.")).toBeInTheDocument();
    expect(within(fb).queryByText(/^The in-app help differed/)).toBeNull();
    const rows = screen.getByRole("heading", { name: "Your attempts" }).closest("section, div") as HTMLElement;
    const row = within(rows).getAllByRole("listitem").find((li) => li.textContent?.includes("Partly comparable"))!;
    expect(row).toHaveTextContent("Partly comparable with the one before");
    expect(within(rows).getAllByRole("listitem").filter((li) => li.textContent?.includes("with the one before"))).toHaveLength(1);
  });

  it("when the points don't compare, the drill shows no point-by-point change", async () => {
    signIn();
    const explanation = "Not comparable: the drill's points changed in between (version 1, now 2); each keeps its own result. (Comparison rules v1)";
    serveDrill([drillAttempt("d2", "2026-11-15T09:20:00Z", compared("incompatible", explanation, "2 of 2 points there", "1 of 3 points there", false), [
      "These attempts were checked with different rubric versions, so they aren't compared.",
    ])]);
    renderApp("/drills/example?attempt=d2", { signedIn: true });
    const fb = await screen.findByRole("region", { name: /Feedback on your attempt from/ });
    expect(within(fb).getByText(explanation)).toBeInTheDocument();
    expect(within(fb).getByText("This one:").closest("li")).toHaveTextContent("1 of 3 points there");
    expect(within(fb).queryByRole("heading", { name: "Point by point" })).toBeNull();
    expect(screen.getByRole("button", { name: /Nov 15, 2026/ }).closest("li")).toHaveTextContent("Not comparable with the one before");
  });

  it("a whiteboard attempt shows its comparison on its feedback and the outcome in its row", async () => {
    signIn("software-engineer");
    const W = `${API}/api/v1/me/whiteboard`;
    const prompts: WhiteboardPromptList = {
      note: "System-design prompts.",
      prompts: [{ id: "sd-url-shortener", version: 1, title: "Design a URL shortener", objective: "Explain it.", brief: "Short links.", requirements: [{ id: "store", text: "Where the mapping is stored" }] }],
    };
    const draft: WhiteboardDraft = {
      prompt_id: "sd-url-shortener", explanation: "", revision: 0, updated_at: null, differs_from_last_attempt: false,
      diagram: { format: "codecoach-whiteboard", version: 1, nodes: [], edges: [], notes: { assumptions: "", requirements: "", capacity: "", tradeoffs: "" } },
    };
    const explanation = "Comparable: the same prompt and version, checked by the same fixed rules, with the same in-app help. (Comparison rules v1)";
    const c = compared("comparable", explanation, "0 of 1 points addressed", "1 of 1 points addressed");
    const row: WhiteboardAttemptSummary = { id: "w2", prompt_version: 1, rubric_version: 1, digest: "x", addressed: 1, total: 1, created_at: "2026-11-15T09:30:00Z", conditions: none, compared: c };
    const full: WhiteboardAttempt = {
      id: "w2", prompt_id: "sd-url-shortener", prompt_version: 1, rubric_version: 1, digest: "x", explanation: "A key-value store.", created_at: "2026-11-15T09:30:00Z",
      diagram: draft.diagram, conditions: none, compared: c,
      feedback: { checks: [], rubric: [{ requirement: "store", text: "Where the mapping is stored", addressed: true, evidence: [] }], reasoning: [], limitations: [] },
    };
    server.use(
      http.get(`${W}/prompts`, () => HttpResponse.json(prompts)),
      http.get(`${W}/sd-url-shortener/draft`, () => HttpResponse.json(draft)),
      http.get(`${W}/sd-url-shortener/attempts`, () => HttpResponse.json([row])),
      http.get(`${W}/attempts/w2`, () => HttpResponse.json(full)),
    );
    const { user } = renderApp("/whiteboard/sd-url-shortener", { signedIn: true });
    const link = await screen.findByRole("button", { name: /Nov 15, 2026/ });
    expect(link.closest("li")).toHaveTextContent("Comparable with the one before");
    await user.click(link);
    const fb = await screen.findByRole("region", { name: /Feedback on the attempt from/ });
    const block = within(fb).getByRole("region", { name: "Compared with your previous attempt" });
    expect(block).toHaveTextContent(/Earlier, .*: 0 of 1 points addressed/);
    expect(block).toHaveTextContent("This one: 1 of 1 points addressed");
    expect(block).toHaveTextContent(explanation);
  });

  it("a work sample shows its comparison under its feedback and the outcome in its row", async () => {
    signIn("software-engineer");
    const ID = "ws-incident-update";
    const brief: WorkSampleBrief = {
      id: ID, version: 1, title: "Checkout errors: the first status update", format: "incident_update", format_label: "Incident status update",
      careers: ["software-engineer"], scenario: "You're the on-call engineer.", audience: "Colleagues.", purpose: "Say what's happening.",
      facts: ["Card payments began failing at 09:12 UTC."], required: ["What is happening"],
      sections: [{ id: "happening", label: "What's happening", hint: "One or two sentences." }],
      min_words: 10, max_words: 180, review_status: "Fictional practice brief.", scope_note: "Everything here is made up for practice.",
    };
    const draft: WorkSampleDraft = { brief_id: ID, sections: { happening: "" }, revision: 0, updated_at: null };
    const explanation = "Can't tell whether these compare: in-app help before one of them wasn't recorded (it's recorded from 15 Nov 2026). (Comparison rules v1)";
    const c = compared("unknown", explanation, "1 of 3 points covered", "3 of 3 points covered");
    const full: WorkSampleAttempt = {
      id: "ws2", brief_id: ID, brief_version: 1, current_version: 1, title: brief.title, format_label: brief.format_label,
      sections: { happening: "Card payments at checkout are failing since 09:12 UTC." }, section_labels: { happening: "What's happening" },
      feedback: { rules_version: 1, covered: 3, total: 3, revision: "", method: "Fixed checks against this brief, not AI.", checks: [], points: [], unsupported: [], claims: [], jargon: [], long_sentences: [] } as unknown as WorkSampleAttempt["feedback"],
      reference: { happening: "Since 09:12 UTC, some card payments have been failing." }, revision_of: null, created_at: "2026-11-15T10:00:00Z", conditions: none, compared: c,
    };
    server.use(
      http.get(`${API}/api/v1/work-samples/${ID}`, () => HttpResponse.json(brief)),
      http.get(`${API}/api/v1/me/work-samples/${ID}/draft`, () => HttpResponse.json(draft)),
      http.get(`${API}/api/v1/me/work-samples/${ID}/attempts`, () => HttpResponse.json([{ id: "ws2", brief_version: 1, covered: 3, total: 3, revision_of: null, created_at: full.created_at, conditions: none, compared: c }])),
      http.get(`${API}/api/v1/me/work-samples/attempts/ws2`, () => HttpResponse.json(full)),
    );
    const { user } = renderApp(`/work-samples/${ID}`, { signedIn: true });
    const link = await screen.findByRole("button", { name: /Nov 15, 2026/ });
    expect(link.closest("li")).toHaveTextContent("Can't tell whether it compares with the one before");
    await user.click(link);
    const block = await screen.findByRole("region", { name: "Compared with your previous attempt" });
    expect(block).toHaveTextContent(/Earlier, .*: 1 of 3 points covered/);
    expect(block).toHaveTextContent("This one: 3 of 3 points covered");
    expect(block).toHaveTextContent(explanation);
  });
});
