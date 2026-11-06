/** A fake scenario backend walking a tiny authored graph on the "server" side. */
import { http, HttpResponse } from "msw";

import type { ScenarioAttempt, ScenarioSummary } from "@/api/types";

const API = "http://localhost:8000";
type Graph = Record<string, { kind: "info" | "choice" | "written" | "ending"; title: string; text: string; next?: string; options?: { id: string; label: string; to: string; quality: "strong" | "risky"; feedback: string }[] }>;
const GRAPH: Graph = {
  start: { kind: "info", title: "Start of shift", text: "Two call lights.", next: "who" },
  who: { kind: "choice", title: "Who first?", text: "Choose.", options: [
    { id: "bed3", label: "Bed 3 (breathing)", to: "call", quality: "strong", feedback: "Breathing comes first." },
    { id: "bed7", label: "Bed 7 (pain)", to: "late", quality: "risky", feedback: "Breathing should come first." },
  ] },
  call: { kind: "written", title: "Make the call", text: "Write the SBAR call.", next: "good" },
  late: { kind: "info", title: "Later", text: "He got worse.", next: "bad" },
  good: { kind: "ending", title: "Help is on the way", text: "Team arrives." },
  bad: { kind: "ending", title: "Help arrived late", text: "Delayed." },
};

export const scenarioSummary: ScenarioSummary = {
  id: "rn-two-patients", track: "registered-nurse", career_title: "Registered Nurse", title: "Two call lights at once",
  role: "Medical-surgical nurse", objective: "Decide who to see first.", minutes: 7, scope: "Fictional, not clinically validated.",
  version: 1, regulated: true, validated: false, decisions: 1, endings: 2,
  review: { status: "author_reviewed", by: "CodeCoach project author", on: "2026-11-03", note: "Not reviewed by a nurse educator." },
};

export const scenarioStore = { attempts: [] as ScenarioAttempt[], seq: 0, retire: false };
export function resetScenarioStore() { scenarioStore.attempts = []; scenarioStore.seq = 0; scenarioStore.retire = false; }

function view(a: ScenarioAttempt): ScenarioAttempt {
  const retired = scenarioStore.retire;
  const node = GRAPH[(a as unknown as { node: string }).node]!;
  const current = a.status === "in_progress" && !retired && node.kind !== "ending"
    ? { id: (a as unknown as { node: string }).node, kind: node.kind as "info" | "choice" | "written", title: node.title, text: node.text, options: (node.options ?? []).map(({ id, label }) => ({ id, label })) }
    : null;
  return { ...a, retired, current, scenario: { ...scenarioSummary, version: retired ? 2 : 1 } };
}

const err = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message, request_id: "r", details: null } }, { status });

export const scenarioHandlers = [
  http.get(`${API}/api/v1/scenarios`, () => HttpResponse.json({
    track: "registered-nurse", career_title: "Registered Nurse", scenarios: [scenarioSummary],
    coverage_note: "Scenarios are new and few: Registered Nurse (1) and Software Engineer (1).",
    careers_with_scenarios: [{ track: "registered-nurse", title: "Registered Nurse", scenarios: 1 }, { track: "software-engineer", title: "Software Engineer", scenarios: 1 }],
  })),
  http.get(`${API}/api/v1/scenarios/:id`, () => HttpResponse.json({ ...scenarioSummary, references: [{ title: "SBAR Tool", publisher: "IHI", url: null, published: null, kind: "external", note: "No link recorded." }], changes: ["First version."] })),
  http.get(`${API}/api/v1/me/scenario-attempts`, () => HttpResponse.json(scenarioStore.attempts.map((a) => ({
    id: a.id, scenario_id: "rn-two-patients", title: "Two call lights at once", version: 1, mode: a.mode, status: a.status,
    outcome: a.debrief?.outcome ?? null, retired: scenarioStore.retire, created_at: a.created_at, completed_at: a.completed_at,
  })))),
  http.post(`${API}/api/v1/me/scenarios/:id/attempts`, async ({ request }) => {
    const body = (await request.json()) as { mode: "assessed" | "exploration"; parent_id?: string };
    const open = scenarioStore.attempts.find((a) => a.mode === "assessed" && a.status === "in_progress");
    if (body.mode === "assessed" && open) return HttpResponse.json(view(open));
    const now = new Date().toISOString();
    const a = { id: `att-${++scenarioStore.seq}`, version: 1, mode: body.mode, parent_id: body.parent_id ?? null, status: "in_progress", steps: [], debrief: null,
      created_at: now, updated_at: now, completed_at: null, node: "start" } as unknown as ScenarioAttempt;
    scenarioStore.attempts.unshift(a);
    return HttpResponse.json(view(a));
  }),
  http.get(`${API}/api/v1/me/scenario-attempts/:id`, ({ params }) => {
    const a = scenarioStore.attempts.find((x) => x.id === params.id);
    return a ? HttpResponse.json(view(a)) : err(404, "not_found", "Attempt not found");
  }),
  http.post(`${API}/api/v1/me/scenario-attempts/:id/steps`, async ({ params, request }) => {
    const a = scenarioStore.attempts.find((x) => x.id === params.id) as (ScenarioAttempt & { node: string }) | undefined;
    if (!a) return err(404, "not_found", "Attempt not found");
    if (scenarioStore.retire) return err(409, "scenario_updated", "This scenario was updated to version 2.");
    const body = (await request.json()) as { node_id: string; choice_id?: string; text?: string };
    if (body.node_id !== a.node) return err(409, "stale_step", "That step isn't the current one. Reload to see where you are.");
    const node = GRAPH[a.node]!;
    const at = new Date().toISOString();
    let next = node.next;
    if (node.kind === "choice") {
      const o = node.options!.find((x) => x.id === body.choice_id);
      if (!o) return err(400, "invalid_choice", "Choose one of the options shown.");
      a.steps.push({ node_id: a.node, kind: "choice", title: node.title, text: node.text, choice_id: o.id, choice_label: o.label, quality: o.quality, feedback: o.feedback, covered: [], missing: [], at });
      next = o.to;
    } else if (node.kind === "written") {
      a.steps.push({ node_id: a.node, kind: "written", title: node.title, text: node.text, response: body.text, covered: ["Situation"], missing: ["Recommendation"], at });
    } else {
      a.steps.push({ node_id: a.node, kind: "info", title: node.title, text: node.text, covered: [], missing: [], at });
    }
    a.node = next!;
    const target = GRAPH[a.node]!;
    if (target.kind === "ending") {
      a.status = "completed";
      a.completed_at = at;
      const choice = a.steps.findIndex((s) => s.kind === "choice");
      a.debrief = {
        outcome: `${target.title} (simulated)`, ending_title: target.title, ending_text: target.text, summary: "Debrief text.",
        path: [...a.steps.map((s) => s.title), target.title],
        decisions: [{ step_index: choice, title: "Who first?", chosen: a.steps[choice]!.choice_label!, quality: a.steps[choice]!.quality!, rule: a.steps[choice]!.feedback!,
          alternatives: [{ label: "The other bed", quality: "risky", rule: "Alternative rule." }] }],
        strengths: [], written: [], references: [], feedback_source: "All feedback here is the scenario's authored decision rules. No AI commentary was generated.",
        disclaimer: "Outcomes are simulated consequences of a fictional case.",
      };
    }
    return HttpResponse.json(view(a));
  }),
];
