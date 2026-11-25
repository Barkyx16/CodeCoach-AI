import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { AttemptConditions, Drill, DrillAttempt, ScenarioAttempt, WhiteboardAttempt, WhiteboardAttemptSummary, WhiteboardDraft, WhiteboardPromptList } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { scenarioSummary } from "../scenarios";
import { API, server } from "../server";

/**
 * The conditions of drills, scenario runs and whiteboard attempts (Volume 14, prompt 4;
 * docs/ATTEMPT_CONDITIONS.md): each attempt's page and its row in the attempts list say what in-app
 * help came before it, with the labels every format uses, as the server gives them.
 */
const NOTE = "Only help shown in CodeCoach is recorded. Help from anywhere else isn't known, and accessibility settings such as dictation or captions are never counted as help.";
const hint: AttemptConditions = {
  labels: ["Hint shown"], recorded_from: "2026-11-15", note: NOTE, round: null,
  help: [{ label: "Hint shown", detail: "Lesson “Structuring a behavioral answer with STAR” read", at: "2026-11-15T09:00:00Z" }],
};
const none: AttemptConditions = { labels: ["No in-app help recorded"], recorded_from: "2026-11-15", note: NOTE, help: [], round: null };
const unknown: AttemptConditions = { labels: ["Not recorded"], recorded_from: "2026-11-15", note: NOTE, help: [], round: null };
const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));

const D = `${API}/api/v1/me/drills`;
const example: Drill = {
  id: "example", title: "Answer with a concrete example", objective: "One specific example, not a general statement.",
  looks_for: ["Answers the question", "One specific situation"], target_seconds: null, prompt: "Tell me about a time patient assessment really mattered.", attempts: 2,
};
const drillAttempt = (id: string, at: string, conditions: AttemptConditions, compared: string[] | null): DrillAttempt => ({
  id, drill_id: "example", prompt: example.prompt, text: "When two patients needed me at once I saw the one short of breath first.", source: "typed",
  spoken_seconds: null, rubric_version: 1, created_at: at, compared_with_previous: compared, conditions,
  feedback: {
    rubric_version: 1,
    observations: [{ point: "Answers the question", present: true, detail: "It answers it" }, { point: "One specific situation", present: true, detail: "One situation" }],
    generalities: [], measured: { words: 14, reading_estimate_seconds: 6 }, notes: [], limitations: "Built-in rules.",
  },
});

describe("Conditions of drills, scenarios and whiteboards", () => {
  it("a drill attempt says the lesson before it; the next one says none, and its comparison says the help differed", async () => {
    asNurse();
    const first = drillAttempt("d1", "2026-11-15T09:05:00Z", hint, null);
    const second = drillAttempt("d2", "2026-11-15T09:20:00Z", none, [
      "The same points are there as last time.",
      "The in-app help differed: before the earlier one, hint shown; before this one, none recorded.",
    ]);
    server.use(
      http.get(`${D}/example`, () => HttpResponse.json(example)),
      http.get(`${D}/example/attempts`, () => HttpResponse.json([second, first])),
    );
    renderApp("/drills/example?attempt=d1", { signedIn: true });
    const fb = await screen.findByRole("region", { name: /Feedback on your attempt from/ });
    expect(within(fb).getByText(/In-app help before this attempt:/).closest("p")).toHaveTextContent("In-app help before this attempt: Hint shown");
    expect(within(fb).getByText(/Lesson “Structuring a behavioral answer with STAR” read/)).toBeInTheDocument();
    const history = screen.getByRole("heading", { name: "Your attempts" }).closest("section, div")!;
    expect(history).toHaveTextContent("In-app help: Hint shown");
    expect(history).toHaveTextContent("In-app help: No in-app help recorded");
  });

  it("the later drill attempt's comparison names the help that differed", async () => {
    asNurse();
    const second = drillAttempt("d2", "2026-11-15T09:20:00Z", none, ["The in-app help differed: before the earlier one, hint shown; before this one, none recorded."]);
    server.use(
      http.get(`${D}/example`, () => HttpResponse.json(example)),
      http.get(`${D}/example/attempts`, () => HttpResponse.json([second])),
    );
    renderApp("/drills/example?attempt=d2", { signedIn: true });
    expect(await screen.findByText("The in-app help differed: before the earlier one, hint shown; before this one, none recorded.")).toBeInTheDocument();
  });

  it("an attempt from before recording began says so, with the date", async () => {
    asNurse();
    server.use(
      http.get(`${D}/example`, () => HttpResponse.json(example)),
      http.get(`${D}/example/attempts`, () => HttpResponse.json([drillAttempt("d0", "2026-11-10T09:00:00Z", unknown, null)])),
    );
    renderApp("/drills/example?attempt=d0", { signedIn: true });
    const fb = await screen.findByRole("region", { name: /Feedback on your attempt from/ });
    expect(within(fb).getByText(/In-app help before this attempt:/).closest("p")).toHaveTextContent(/Not recorded \(help is recorded from Sun, Nov 15, 2026\)/);
  });

  it("a scenario run says the lesson before it, and its row in your attempts says the same", async () => {
    asNurse();
    const run: ScenarioAttempt = {
      id: "run-1", scenario: { ...scenarioSummary }, version: 1, mode: "assessed", parent_id: null, retired: false, status: "in_progress",
      current: { id: "start", kind: "info", title: "Start of shift", text: "Two call lights.", options: [], clock: null, tasks: [] },
      steps: [], debrief: null, created_at: "2026-11-15T09:10:00Z", updated_at: "2026-11-15T09:10:00Z", completed_at: null,
      conditions: { ...hint, help: [{ label: "Hint shown", detail: "Lesson “Prioritizing when several patients need you” read", at: "2026-11-15T09:00:00Z" }] },
    };
    server.use(http.get(`${API}/api/v1/me/scenario-attempts/run-1`, () => HttpResponse.json(run)));
    renderApp("/scenarios/attempts/run-1", { signedIn: true });
    expect(await screen.findByText(/Lesson “Prioritizing when several patients need you” read/)).toBeInTheDocument();
    expect(screen.getByText(/In-app help before this attempt:/).closest("p")).toHaveTextContent("Hint shown");
  });

  it("a whiteboard attempt says there was none, in its row and on its feedback", async () => {
    server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: baseUser }))));
    const W = `${API}/api/v1/me/whiteboard`;
    const prompts: WhiteboardPromptList = {
      note: "System-design prompts.",
      prompts: [{ id: "sd-url-shortener", version: 1, title: "Design a URL shortener", objective: "Explain it.", brief: "Short links.", requirements: [{ id: "store", text: "Where the mapping is stored" }] }],
    };
    const draft: WhiteboardDraft = {
      prompt_id: "sd-url-shortener", explanation: "", revision: 0, updated_at: null, differs_from_last_attempt: false,
      diagram: { format: "codecoach-whiteboard", version: 1, nodes: [], edges: [], notes: { assumptions: "", requirements: "", capacity: "", tradeoffs: "" } },
    };
    const row: WhiteboardAttemptSummary = { id: "w1", prompt_version: 1, rubric_version: 1, digest: "x", addressed: 1, total: 1, created_at: "2026-11-15T09:30:00Z", conditions: none };
    const full: WhiteboardAttempt = {
      id: "w1", prompt_id: "sd-url-shortener", prompt_version: 1, rubric_version: 1, digest: "x", explanation: "A key-value store.", created_at: "2026-11-15T09:30:00Z",
      diagram: draft.diagram, conditions: none,
      feedback: { checks: [], rubric: [{ requirement: "store", text: "Where the mapping is stored", addressed: true, evidence: [] }], reasoning: [], limitations: [] },
    };
    server.use(
      http.get(`${W}/prompts`, () => HttpResponse.json(prompts)),
      http.get(`${W}/sd-url-shortener/draft`, () => HttpResponse.json(draft)),
      http.get(`${W}/sd-url-shortener/attempts`, () => HttpResponse.json([row])),
      http.get(`${W}/attempts/w1`, () => HttpResponse.json(full)),
    );
    const { user } = renderApp("/whiteboard/sd-url-shortener", { signedIn: true });
    const link = await screen.findByRole("button", { name: /Nov 15, 2026/ });
    expect(link.closest("li")).toHaveTextContent("In-app help: No in-app help recorded");
    await user.click(link);
    const fb = await screen.findByRole("region", { name: /Feedback on the attempt from/ });
    expect(within(fb).getByText(/In-app help before this attempt:/).closest("p")).toHaveTextContent("No in-app help recorded");
  });
});
