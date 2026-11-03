/** A fake Learn backend: one nursing unit with a prerequisite, server-side grading, versions. */
import { http, HttpResponse } from "msw";

import type { LearnUnit, UnitProgress } from "@/api/types";

const API = "http://localhost:8000";
const ANSWERS: Record<string, number> = { q1: 1, q2: 1 };

export const learnStore = { events: [] as UnitProgress["events"], version: 1 };
export function resetLearnStore() {
  learnStore.events = [];
  learnStore.version = 1;
}

export function sbarUnit(): LearnUnit {
  return {
    id: "rn-prioritization", track: "registered-nurse", title: "Prioritizing when several patients need you",
    skill: "Judgment under pressure", topics: [], minutes: 8, objective: "Explain how you decide who to see first.",
    prerequisites: [{ id: "rn-sbar-handoff", title: "SBAR for handoffs and escalation" }], version: learnStore.version,
    review_status: "author_reviewed", regulated: true, career_title: "Registered Nurse",
    changes: learnStore.version === 1 ? ["First version."] : ["First version.", "Added a reassessment step."],
    scope_note: "Interview education, not clinical guidance. Follow your jurisdiction's scope of practice.",
    explanation: ["Airway, breathing and circulation come first."],
    example: { title: "Two call lights", intro: "Short of breath vs pain medicine.", code: null, language: null, walkthrough: ["See the breathing problem first."] },
    mistakes: ["Picking an order without saying why."],
    exercise: {
      prompt: "An oxygen alarm and a bathroom request: who first?", draft_label: "Your answer",
      guided_steps: ["Which could become life-threatening?", "ABCs first.", "Ask an assistant to help.", "Go to the alarm, then reassess."],
      solution: "The oxygen alarm comes first.", solution_language: null,
    },
    check: [
      { id: "q1", prompt: "Which concern comes first?", options: ["Discharge question", "Labored breathing", "Dressing change"] },
      { id: "q2", prompt: "What else shows safe judgment?", options: ["Never asking for help", "Escalating appropriately", "Quoting doses"] },
    ],
    pass_rule: "Every answer in the check is right.",
    practice: { kind: "question", ref_id: "m-pressure-0", label: "Answer “Patient assessment under pressure”", href: "/careers/registered-nurse/questions/m-pressure-0" },
    references: [
      { title: "Clinical Judgment Measurement Model (NCSBN)", publisher: "National Council of State Boards of Nursing", url: null, published: null, kind: "external", note: "No link recorded." },
      { title: "Scenario rubric", publisher: "CodeCoach repository", url: null, published: null, kind: "repository", note: "backend/app/careers/questions.py" },
    ],
    review: { status: "author_reviewed", by: "CodeCoach project author", on: "2026-11-02", note: "Not reviewed by a licensed nurse educator." },
    question_ids: ["m-pressure-0"],
  };
}

function progress(): UnitProgress {
  const v = learnStore.version;
  const cur = learnStore.events.filter((e) => e.version === v);
  const read = cur.some((e) => e.kind === "read");
  const passed = cur.some((e) => e.kind === "check_passed");
  return {
    unit_id: "rn-prioritization", current_version: v, versions_used: [...new Set(learnStore.events.map((e) => e.version))].sort(),
    started: learnStore.events.some((e) => e.kind === "started"), read, check_attempts: cur.filter((e) => e.kind === "check_attempted").length,
    check_passed: passed, passed_versions: [...new Set(learnStore.events.filter((e) => e.kind === "check_passed").map((e) => e.version))],
    practiced: false, practiced_evidence: null, events: learnStore.events,
    next_action: !read ? { kind: "read", label: "Read the unit, then mark it read" } : !passed ? { kind: "check", label: "Take the comprehension check" } : { kind: "practice", label: "Answer “Patient assessment under pressure”" },
  };
}

function record(kind: UnitProgress["events"][number]["kind"], detail: string | null = null) {
  const once = kind !== "check_attempted";
  if (once && learnStore.events.some((e) => e.kind === kind && e.version === learnStore.version)) return;
  learnStore.events.push({ kind, version: learnStore.version, at: new Date().toISOString(), detail });
}

const changed = () => HttpResponse.json({ error: { code: "unit_changed", message: "This unit was updated.", request_id: "r", details: { current_version: learnStore.version } } }, { status: 409 });

export const learnHandlers = [
  http.get(`${API}/api/v1/learn`, ({ request }) => {
    const track = new URL(request.url).searchParams.get("track");
    const u = sbarUnit();
    const units = track === "registered-nurse" ? [
      { ...u, id: "rn-sbar-handoff", title: "SBAR for handoffs and escalation", prerequisites: [], skill: "shift handoffs" },
      u,
    ].map(({ id, track: t, title, skill, topics, minutes, objective, prerequisites, version, review_status, regulated }) =>
      ({ id, track: t, title, skill, topics, minutes, objective, prerequisites, version, review_status, regulated })) : [];
    return HttpResponse.json({
      track, career_title: track === "registered-nurse" ? "Registered Nurse" : "Software Engineer", units,
      coverage_note: `Learn mode is new and deliberately small: units exist for Registered Nurse (3) and Software Engineer (3).${units.length ? "" : " Software Engineer doesn't have any yet."}`,
      careers_with_units: [{ track: "registered-nurse", title: "Registered Nurse", units: 3 }, { track: "software-engineer", title: "Software Engineer", units: 3 }],
    });
  }),
  http.get(`${API}/api/v1/learn/related`, ({ request }) => {
    const q = new URL(request.url).searchParams.get("question_id");
    return HttpResponse.json(q === "m-pressure-0" ? [{ id: "rn-prioritization", title: "Prioritizing when several patients need you" }] : []);
  }),
  http.get(`${API}/api/v1/learn/units/:id`, ({ params }) => (params.id === "rn-prioritization"
    ? HttpResponse.json(sbarUnit())
    : HttpResponse.json({ error: { code: "not_found", message: "Learning unit not found", request_id: "r", details: null } }, { status: 404 }))),
  http.get(`${API}/api/v1/me/learn`, () => HttpResponse.json({ "rn-sbar-handoff": { ...progress(), unit_id: "rn-sbar-handoff", started: false, read: false } })),
  http.get(`${API}/api/v1/me/learn/units/:id`, () => HttpResponse.json(progress())),
  http.post(`${API}/api/v1/me/learn/units/:id/events`, async ({ request }) => {
    const body = (await request.json()) as { kind: "started" | "read"; version: number };
    if (body.version !== learnStore.version) return changed();
    if (body.kind === "read") record("started");
    record(body.kind);
    return HttpResponse.json(progress());
  }),
  http.post(`${API}/api/v1/me/learn/units/:id/check`, async ({ request }) => {
    const body = (await request.json()) as { version: number; answers: Record<string, number> };
    if (body.version !== learnStore.version) return changed();
    const results = Object.entries(ANSWERS).map(([id, answer]) => ({
      id, chosen: body.answers[id] ?? null, correct: body.answers[id] === answer, answer, explanation: `Because of ${id}.`,
    }));
    const correct = results.filter((r) => r.correct).length;
    record("started");
    record("check_attempted", `${correct} of 2 right`);
    if (correct === 2) record("check_passed", "every answer right");
    return HttpResponse.json({ passed: correct === 2, correct, total: 2, pass_rule: "Every answer in the check is right.", results, progress: progress() });
  }),
];
