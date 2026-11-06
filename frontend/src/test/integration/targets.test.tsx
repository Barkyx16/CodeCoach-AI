import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Requirement, Target } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = new Date().toISOString();

const requirement = (over: Partial<Requirement>): Requirement => ({
  id: "r-1", category: "responsibility", text: "Perform patient assessment and triage", origin: "explicit",
  quote: "- Perform patient assessment and triage for incoming patients", quote_in_description: true,
  skills: ["patient assessment", "triage"], removed: false,
  coverage: { level: "limited", label: "Limited evidence: not practised yet", answers: 0, questions_answered: 0, average_best_score: null, judged_attempts: 0, passed: 0 },
  practice: [{ kind: "question", title: "What good patient assessment looks like", href: "/careers/registered-nurse/questions/e-good-0", why: "Practises patient assessment", answered: false, best_score: null }],
  ...over,
});

function makeTarget(): Target {
  return {
    id: "t-1", title: "ED Nurse", employer: "Mercy General", track: "registered-nurse", career_title: "Registered Nurse",
    interview_date: null, archived: false, selected: true, requirements: 3, gaps: 1, created_at: now, updated_at: now,
    description: "Responsibilities:\n- Perform patient assessment and triage for incoming patients\nRequirements\n- Current RN license",
    notes: null, extractor: "rule-based (no AI)",
    requirement_list: [
      requirement({}),
      requirement({
        id: "r-2", category: "required_skill", text: "Current RN license", quote: "- Current RN license", skills: [], practice: [],
        coverage: { level: "gap", label: "A qualification or experience requirement; practice questions can't cover it", answers: 0, questions_answered: 0, average_best_score: null, judged_attempts: 0, passed: 0 },
      }),
      requirement({ id: "r-3", category: "required_skill", text: "Care planning", origin: "inferred", quote: null, quote_in_description: false, skills: ["care planning"] }),
    ],
    next_activity: { kind: "question", title: "What good patient assessment looks like", href: "/careers/registered-nurse/questions/e-good-0", why: "“Perform patient assessment and triage” has limited evidence. Practises patient assessment.", answered: false, best_score: null },
    targeted_session: { title: "Short targeted session", scope: "1 question on requirements with the least practice.", round: { track: "registered-nurse", question_ids: ["e-good-0"], duration_minutes: 10, purpose: "practice", difficulty: null } },
    mock_interview: { title: "Mock interview for ED Nurse", scope: "2 questions chosen to cover: Perform patient assessment and triage; Care planning. Questions come from the Registered Nurse question bank. They are practice questions, not this employer's.", round: { track: "registered-nurse", question_ids: ["e-good-0", "e-time-0"], duration_minutes: 15, purpose: "practice", difficulty: null } },
    recent_attempts: [], experience: [], days_to_interview: null,
  };
}

function targetServer() {
  let target = makeTarget();
  const calls: { method: string; path: string; body: unknown }[] = [];
  const record = async (request: Request, path: string) => {
    const body = request.method === "GET" || request.method === "DELETE" ? null : await request.json();
    calls.push({ method: request.method, path, body });
    return body as Record<string, unknown>;
  };
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/targets`, () => HttpResponse.json([target])),
    http.post(`${API}/api/v1/targets`, async ({ request }) => { await record(request, "create"); return HttpResponse.json(target, { status: 201 }); }),
    http.get(`${API}/api/v1/targets/t-1`, () => HttpResponse.json(target)),
    http.patch(`${API}/api/v1/targets/t-1/requirements/:rid`, async ({ request, params }) => {
      const body = await record(request, `requirement:${String(params.rid)}`);
      target = { ...target, requirement_list: target.requirement_list.map((r) => (r.id === params.rid ? { ...r, ...body } : r)) };
      return HttpResponse.json(target);
    }),
    http.post(`${API}/api/v1/targets/t-1/experience`, async ({ request }) => {
      const body = await record(request, "experience");
      target = { ...target, experience: [{ id: "x-1", created_at: now, updated_at: now, situation: "", action: "", result: "", requirement_ids: [], ...(body as object), title: String(body.title) }] };
      return HttpResponse.json(target);
    }),
    http.post(`${API}/api/v1/interviews`, async ({ request }) => { await record(request, "interview"); return HttpResponse.json({ id: "round-t" }, { status: 201 }); }),
  );
  return calls;
}

describe("Prepare for this role", () => {
  it("pastes a posting and opens its workspace", async () => {
    const calls = targetServer();
    const { user, router } = renderApp("/targets", { signedIn: true });
    expect(await screen.findByRole("link", { name: /ED Nurse/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add a target role" }));
    await user.type(screen.getByLabelText("Role title"), "ED Nurse");
    await user.type(screen.getByLabelText("Job description"), "Responsibilities:{enter}- Perform patient assessment");
    await user.click(screen.getByRole("button", { name: "Find requirements" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/targets/t-1"));
    expect(calls[0]).toMatchObject({ path: "create", body: { title: "ED Nurse", track: "registered-nurse", description: "Responsibilities:\n- Perform patient assessment" } });
  });

  it("shows each requirement's source, origin, honest coverage and gaps", async () => {
    targetServer();
    const { user } = renderApp("/targets/t-1", { signedIn: true });
    const triage = await screen.findByRole("article", { name: "Perform patient assessment and triage" });
    expect(within(triage).getByText(/From the posting · Practises: patient assessment, triage/)).toBeInTheDocument();
    expect(within(triage).getByText("Limited evidence: not practised yet")).toBeInTheDocument();
    await user.click(within(triage).getByText("Source text"));
    expect(within(triage).getByText("- Perform patient assessment and triage for incoming patients")).toBeVisible();
    const licence = screen.getByRole("article", { name: "Current RN license" });
    expect(within(licence).getByText(/qualification or experience requirement/)).toBeInTheDocument();
    expect(within(licence).getByText(/No matching skill in the question bank/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Suggested for Registered Nurse roles \(not in this posting\)/ })).toBeInTheDocument();
    expect(screen.getByText(/not a chance of getting the job/)).toBeInTheDocument();
  });

  it("corrects and removes requirements, and the view filter lives in the URL", async () => {
    const calls = targetServer();
    const { user, router } = renderApp("/targets/t-1", { signedIn: true });
    const triage = await screen.findByRole("article", { name: "Perform patient assessment and triage" });
    await user.click(within(triage).getByRole("button", { name: "Correct" }));
    const input = within(triage).getByLabelText("Requirement");
    await user.clear(input);
    await user.type(input, "Assess and triage ED patients");
    await user.click(within(triage).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ path: "requirement:r-1", body: { text: "Assess and triage ED patients" } }));
    const licence = screen.getByRole("article", { name: "Current RN license" });
    await user.click(within(licence).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ path: "requirement:r-2", body: { removed: true } }));
    await user.click(screen.getByRole("link", { name: /^Removed \(1\)/ }));
    expect(router.state.location.search).toBe("?show=removed");
    expect(await screen.findByRole("button", { name: "Restore" })).toBeInTheDocument();
  });

  it("explains a mock interview's scope before starting it, then starts a real round", async () => {
    const calls = targetServer();
    const { user, router } = renderApp("/targets/t-1", { signedIn: true });
    await user.click(await screen.findByText("Mock interview for ED Nurse"));
    expect(screen.getByText(/not this employer's/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Start (2 questions, 15 min)" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/interviews/round-t"));
    expect(calls.at(-1)?.body).toMatchObject({ kind: "questions", track: "registered-nurse", question_ids: ["e-good-0", "e-time-0"] });
  });

  it("practice links come back to the same filtered workspace", async () => {
    targetServer();
    const { user, router } = renderApp("/targets/t-1?show=limited", { signedIn: true });
    const triage = await screen.findByRole("article", { name: "Perform patient assessment and triage" });
    await user.click(within(triage).getByRole("link", { name: "What good patient assessment looks like" }));
    expect(router.state.location.pathname).toBe("/careers/registered-nurse/questions/e-good-0");
    await user.click(await screen.findByRole("link", { name: "Back to this role" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/targets/t-1"));
    expect(router.state.location.search).toBe("?show=limited");
  });

  it("adds the learner's own example linked to a requirement, without rewriting it", async () => {
    const calls = targetServer();
    const { user } = renderApp("/targets/t-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Add an example" }));
    const form = screen.getByRole("form", { name: "New example" });
    await user.type(within(form).getByLabelText("Short title"), "Night shift deterioration");
    await user.type(within(form).getByLabelText("Result (optional)"), "Stable in 30 minutes.");
    await user.click(within(form).getByRole("checkbox", { name: "Perform patient assessment and triage" }));
    await user.click(within(form).getByRole("button", { name: "Save example" }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({
      path: "experience", body: { title: "Night shift deterioration", result: "Stable in 30 minutes.", requirement_ids: ["r-1"] },
    }));
    expect(await screen.findByText("Stable in 30 minutes.")).toBeInTheDocument();
  });
});
