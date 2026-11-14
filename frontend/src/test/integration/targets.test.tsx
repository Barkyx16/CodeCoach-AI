import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Freshness, Requirement, RequirementSetIn, RevisionPreview, Target } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = new Date().toISOString();

const requirement = (over: Partial<Requirement>): Requirement => ({
  id: "r-1", category: "responsibility", text: "Perform patient assessment and triage", version: 1, origin: "explicit",
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
    recent_attempts: [], experience: [], days_to_interview: null, requirements_revision: 1,
  };
}

function targetServer(over: Partial<Target> = {}) {
  let target = { ...makeTarget(), ...over };
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
      target = { ...target, experience: [{ id: "x-1", revision: 1, created_at: now, updated_at: now, situation: "", action: "", result: "", requirement_ids: [], ...(body as object), title: String(body.title) }] };
      return HttpResponse.json(target);
    }),
    http.post(`${API}/api/v1/interviews`, async ({ request }) => { await record(request, "interview"); return HttpResponse.json({ id: "round-t" }, { status: 201 }); }),
    http.post(`${API}/api/v1/targets/t-1/experience/:eid/requirements/:rid/reuse`, ({ params }) => {
      calls.push({ method: "POST", path: `reuse-story:${String(params.eid)}:${String(params.rid)}`, body: null });
      return HttpResponse.json(target);
    }),
    http.post(`${API}/api/v1/targets/t-1/actions/:aid/requirements/:rid/reuse`, ({ params }) => {
      calls.push({ method: "POST", path: `reuse-action:${String(params.aid)}:${String(params.rid)}`, body: null });
      return HttpResponse.json(target);
    }),
    http.get(`${API}/api/v1/targets/t-1/requirements/:rid/history`, ({ params }) => {
      calls.push({ method: "GET", path: `history:${String(params.rid)}`, body: null });
      return HttpResponse.json([
        { version: 1, state: "original", text: "Perform patient assessment", category: "responsibility", at: null, same_as: null },
        { version: 2, state: "changed", text: "Perform patient assessment and triage", category: "responsibility", at: now, same_as: null },
      ]);
    }),
    // The whole-set preview and save (docs/REQUIREMENT_VERSIONS.md), simplified: case, spacing and
    // punctuation are cosmetic; anything else is a change.
    http.post(`${API}/api/v1/targets/t-1/requirements/revision/preview`, async ({ request }) => {
      const body = (await record(request, "preview")) as unknown as RequirementSetIn;
      return HttpResponse.json(previewOf(target, body));
    }),
    http.put(`${API}/api/v1/targets/t-1/requirements`, async ({ request }) => {
      const body = (await record(request, "save")) as unknown as RequirementSetIn;
      if (body.expected_revision !== target.requirements_revision) {
        return HttpResponse.json({ error: { code: "stale_revision", message: "These requirements were changed somewhere else.", details: { current: target } } }, { status: 409 });
      }
      const changes = previewOf(target, body).changes;
      target = {
        ...target,
        requirements_revision: target.requirements_revision + 1,
        requirement_list: target.requirement_list.map((r) => {
          const c = changes.find((x) => x.requirement_id === r.id);
          const item = body.items.find((x) => x.id === r.id)!;
          return { ...r, text: item.text, category: item.category, removed: item.removed, version: c?.state === "changed" ? r.version + 1 : r.version };
        }),
      };
      return HttpResponse.json(target);
    }),
  );
  return calls;
}

const plain = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

function previewOf(target: Target, body: RequirementSetIn): RevisionPreview {
  const counts = { changed: 0, added: 0, removed: 0, restored: 0, unchanged: 0 };
  const changes = body.items.map((item, index) => {
    const r = target.requirement_list.find((x) => x.id === item.id);
    let state: RevisionPreview["changes"][number]["state"] = "added";
    if (r) {
      if (item.removed && !r.removed) state = "removed";
      else if (!item.removed && r.removed) state = "restored";
      else if (item.text === r.text && item.category === r.category) state = "unchanged";
      else if (item.category === r.category && plain(item.text) === plain(r.text)) state = "cosmetic";
      else state = "changed";
    }
    counts[state === "cosmetic" ? "unchanged" : state] += 1;
    const affected = r && ["changed", "removed", "restored"].includes(state);
    return {
      index, requirement_id: r?.id ?? null, state, text: item.text,
      previous_text: r && state !== "unchanged" ? r.text : null,
      version_from: r?.version ?? null, version_to: r ? (state === "changed" ? r.version + 1 : r.version) : 1,
      stories: affected ? target.experience.filter((e) => (e.requirement_ids ?? []).includes(r.id)).map((e) => ({ id: e.id, title: e.title })) : [],
      actions: affected ? (target.action_links ?? []).filter((a) => a.requirement_id === r.id).map((a) => ({ id: a.action_id, title: a.title })) : [],
    };
  });
  const summary = `${counts.changed} changed, ${counts.added} added, ${counts.removed} removed${counts.restored ? `, ${counts.restored} restored` : ""}, ${counts.unchanged} unchanged`;
  return { summary, counts, changes, suggestions: [], revision: target.requirements_revision };
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
    // A change of meaning is shown before it's saved, then saved as a change to the set.
    const review = await within(triage).findByRole("region", { name: "Before saving: Perform patient assessment and triage" });
    expect(review).toHaveTextContent("1 changed, 0 added, 0 removed, 2 unchanged");
    await user.click(within(review).getByRole("button", { name: "Save this change" }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ path: "save", body: { expected_revision: 1 } }));
    expect((calls.at(-1)!.body as RequirementSetIn).items.find((i) => i.id === "r-1")).toMatchObject({ text: "Assess and triage ED patients" });
    const licence = await screen.findByRole("article", { name: "Current RN license" });
    await user.click(within(licence).getByRole("button", { name: "Remove" }));
    await user.click(within(await within(licence).findByRole("region", { name: /Before saving/ })).getByRole("button", { name: "Save this change" }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ path: "save", body: { expected_revision: 2 } }));
    expect((calls.at(-1)!.body as RequirementSetIn).items.find((i) => i.id === "r-2")).toMatchObject({ removed: true });
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

describe("Versioned requirements", () => {
  const story = { id: "x-1", revision: 1, created_at: now, updated_at: now, title: "Night shift escalation", situation: "", action: "", result: "", requirement_ids: ["r-1"],
    requirement_links: [{ requirement_id: "r-1", linked_version: 1, current_version: 2, status: "earlier_wording" as const, label: "Linked to an earlier wording (version 1; now version 2)", reused_from: null }] };
  const actionLink = { action_id: "a-1", title: "Lead with the outcome", requirement_id: "r-1", linked_version: 1, current_version: 2, status: "earlier_wording" as const, label: "Linked to an earlier wording (version 1; now version 2)", reused_from: null };
  const versioned = (): Partial<Target> => ({
    requirement_list: makeTarget().requirement_list.map((r) => (r.id === "r-1" ? { ...r, version: 2 } : r)),
    experience: [story], action_links: [actionLink],
  });

  it("a cosmetic correction saves at once, with no review", async () => {
    const calls = targetServer();
    const { user } = renderApp("/targets/t-1", { signedIn: true });
    const triage = await screen.findByRole("article", { name: "Perform patient assessment and triage" });
    await user.click(within(triage).getByRole("button", { name: "Correct" }));
    const input = within(triage).getByLabelText("Requirement");
    await user.clear(input);
    await user.type(input, "Perform patient assessment and triage.");
    await user.click(within(triage).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.at(-1)?.path).toBe("save"));
    expect(screen.queryByRole("region", { name: /Before saving/ })).not.toBeInTheDocument();
  });

  it("the whole set is reviewed before saving: the summary, and the stories and improvements each change affects", async () => {
    const calls = targetServer(versioned());
    const { user } = renderApp("/targets/t-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Edit requirements" }));
    const editor = screen.getByRole("region", { name: "Edit the requirements" });
    const first = within(editor).getByLabelText("Requirement 1");
    await user.clear(first);
    await user.type(first, "Lead triage for incoming patients");
    await user.click(within(editor).getAllByLabelText("Removed")[1]!);
    await user.click(within(editor).getByRole("button", { name: "Add a requirement" }));
    await user.type(within(editor).getByLabelText("Requirement 4 (new)"), "Uses an electronic health record daily");
    expect(calls.some((c) => c.path === "save")).toBe(false);
    await user.click(within(editor).getByRole("button", { name: "Review changes" }));
    const review = await within(editor).findByRole("region", { name: "Changes to save" });
    expect(review).toHaveTextContent("1 changed, 1 added, 1 removed, 1 unchanged");
    const changed = within(review).getByText(/Lead triage for incoming patients/).closest("li")!;
    expect(changed).toHaveTextContent("version 2 → 3");
    expect(changed).toHaveTextContent("Stories linked to it: Night shift escalation.");
    expect(changed).toHaveTextContent("Accepted improvements practising it: Lead with the outcome.");
    expect(changed).toHaveTextContent("They stay linked to the earlier wording until you reuse them.");
    expect(within(review).getByText(/Removed \(its history stays\)/)).toBeInTheDocument();
    await user.click(within(review).getByRole("button", { name: "Save these changes" }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ path: "save", body: { expected_revision: 1, same_as: [] } }));
    await waitFor(() => expect(screen.queryByRole("region", { name: "Edit the requirements" })).not.toBeInTheDocument());
  });

  it("a similar new requirement is only a question: choosing 'the same requirement' is sent, and needs a second review", async () => {
    const calls = targetServer();
    server.use(http.post(`${API}/api/v1/targets/t-1/requirements/revision/preview`, async ({ request }) => {
      const body = (await request.json()) as RequirementSetIn;
      calls.push({ method: "POST", path: "preview", body });
      const index = body.items.length - 1;
      return HttpResponse.json({
        summary: body.same_as?.length ? "1 changed, 0 added, 0 removed, 2 unchanged" : "0 changed, 1 added, 1 removed, 2 unchanged",
        counts: {}, changes: [], revision: 1,
        suggestions: body.same_as?.length ? [] : [{ index, requirement_id: "r-2", text: "Current RN license", question: "This looks like the earlier “Current RN license”. Is it the same requirement?" }],
      });
    }));
    const { user } = renderApp("/targets/t-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Edit requirements" }));
    const editor = screen.getByRole("region", { name: "Edit the requirements" });
    await user.click(within(editor).getAllByLabelText("Removed")[1]!);
    await user.click(within(editor).getByRole("button", { name: "Add a requirement" }));
    await user.type(within(editor).getByLabelText("Requirement 4 (new)"), "A current registered nurse RN license");
    await user.click(within(editor).getByRole("button", { name: "Review changes" }));
    const question = await within(editor).findByRole("group", { name: /Is it the same requirement\?/ });
    expect(within(question).getByLabelText("A different requirement")).toBeChecked(); // nothing is linked unless chosen
    await user.click(within(question).getByLabelText("The same requirement: its next version"));
    expect(within(editor).queryByRole("button", { name: "Save these changes" })).not.toBeInTheDocument();
    await user.click(within(editor).getByRole("button", { name: "Review changes" }));
    expect(await within(editor).findByText("1 changed, 0 added, 0 removed, 2 unchanged")).toBeInTheDocument();
    expect(calls.at(-1)?.body).toMatchObject({ same_as: [{ index: 3, requirement_id: "r-2" }] });
  });

  it("a stale save is refused, shows the saved set beside yours, and keeps your edits", async () => {
    const calls = targetServer({ requirements_revision: 1 });
    const { user } = renderApp("/targets/t-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Edit requirements" }));
    const editor = screen.getByRole("region", { name: "Edit the requirements" });
    const first = within(editor).getByLabelText("Requirement 1");
    await user.clear(first);
    await user.type(first, "Lead triage for incoming patients");
    // Another tab saves first.
    server.use(http.put(`${API}/api/v1/targets/t-1/requirements`, async ({ request }) => {
      const body = (await request.json()) as RequirementSetIn;
      calls.push({ method: "PUT", path: "save", body });
      const saved = { ...makeTarget(), requirements_revision: 2, requirement_list: makeTarget().requirement_list.map((r) => (r.id === "r-3" ? { ...r, text: "Care planning for families" } : r)) };
      if (body.expected_revision !== 2) {
        return HttpResponse.json({ error: { code: "stale_revision", message: "These requirements were changed somewhere else.", details: { current: saved } } }, { status: 409 });
      }
      return HttpResponse.json(saved);
    }));
    await user.click(within(editor).getByRole("button", { name: "Review changes" }));
    await user.click(await within(editor).findByRole("button", { name: "Save these changes" }));
    const stale = await within(editor).findByRole("alert");
    expect(stale).toHaveTextContent("Nothing was saved");
    expect(stale).toHaveTextContent("Care planning for families");
    expect(within(editor).getByLabelText("Requirement 1")).toHaveValue("Lead triage for incoming patients");
    await user.click(within(stale).getByRole("button", { name: "Keep mine and review again" }));
    await user.click(within(editor).getByRole("button", { name: "Review changes" }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ path: "preview", body: { expected_revision: 2 } }));
  });

  it("stories and accepted improvements say they were linked to an earlier wording, and reuse is a deliberate step", async () => {
    const calls = targetServer(versioned());
    const { user } = renderApp("/targets/t-1", { signedIn: true });
    const triage = await screen.findByRole("article", { name: "Perform patient assessment and triage" });
    const improvement = within(triage).getByText("Accepted improvement “Lead with the outcome”").closest("li")!;
    expect(improvement).toHaveTextContent("Linked to an earlier wording (version 1; now version 2)");
    await user.click(within(improvement).getByRole("button", { name: "Use it for the current wording" }));
    await waitFor(() => expect(calls.at(-1)?.path).toBe("reuse-action:a-1:r-1"));
    const storyItem = (await screen.findByText(/Shows “Perform patient assessment and triage”/)).closest("li")!;
    expect(storyItem).toHaveTextContent("Linked to an earlier wording (version 1; now version 2)");
    expect(storyItem.textContent).not.toMatch(/you|your/i); // about the link, never the learner
    await user.click(within(storyItem).getByRole("button", { name: "Use it for the current wording" }));
    await waitFor(() => expect(calls.at(-1)?.path).toBe("reuse-story:x-1:r-1"));
  });

  it("a requirement's history is read when opened; an attempt names the earlier wording it was answered against", async () => {
    const calls = targetServer({
      ...versioned(),
      recent_attempts: [{ answer_id: "ans-1", question_title: "What good patient assessment looks like", score: 64, created_at: now, href: "/careers/registered-nurse/questions/e-good-0?answer=ans-1", requirement_ids: ["r-1"], requirement_versions: { "r-1": 1 } }],
    });
    const { user } = renderApp("/targets/t-1", { signedIn: true });
    const triage = await screen.findByRole("article", { name: "Perform patient assessment and triage" });
    expect(calls.some((c) => c.path.startsWith("history:"))).toBe(false);
    await user.click(within(triage).getByText("History (version 2)"));
    expect(await within(triage).findByText(/Version 1, before the first change: “Perform patient assessment”/)).toBeInTheDocument();
    expect(within(triage).getByText(/Version 2, changed: “Perform patient assessment and triage”/)).toBeInTheDocument();
    expect(screen.getByText(/answered against an earlier wording of “Perform patient assessment and triage” \(version 1; now 2\)/)).toBeInTheDocument();
  });
});

describe("Story freshness on requirement links (docs/STORY_FRESHNESS.md)", () => {
  const needs = {
    state: "needs_review" as const, text: "The story changed since you linked it (version 1, now 2). Review whether it still fits.",
    prepared_revision: 1, current_revision: 2, changes: [{ field: "Result", before: "Stable.", after: "Stable within the hour." }], lineage: [],
  };
  const link = (rid: string, f: Freshness | null) => ({
    requirement_id: rid, linked_version: 1, current_version: 1, status: "current" as const, label: "Linked to the current wording (version 1)", reused_from: null, story_freshness: f,
  });
  const story = {
    id: "x-1", revision: 2, created_at: now, updated_at: now, title: "Night shift escalation", situation: "", action: "", result: "Stable within the hour.",
    requirement_ids: ["r-1", "r-3"], requirement_links: [link("r-1", needs), link("r-3", needs)],
  };

  it("names the links prepared from the earlier version, shows what changed, and refreshes them together when asked", async () => {
    let sent: Record<string, unknown> | null = null;
    targetServer({ experience: [story] });
    server.use(
      http.post(`${API}/api/v1/targets/t-1/experience/x-1/review`, async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        const done = { ...needs, state: "current" as const, text: "Up to date with the story (version 2).", prepared_revision: 2, changes: [] };
        return HttpResponse.json({ ...makeTarget(), experience: [{ ...story, requirement_links: [link("r-1", done), link("r-3", done)] }] });
      }),
    );
    const { user } = renderApp("/targets/t-1", { signedIn: true });
    const note = await screen.findByText("For “Perform patient assessment and triage”, “Care planning”:");
    const box = note.parentElement!.querySelector(".freshness") as HTMLElement;
    expect(box).toHaveTextContent("The story changed since you linked it (version 1, now 2). Review whether it still fits.");
    expect(within(box).getByRole("columnheader", { name: "As linked (version 1)" })).toBeInTheDocument();
    expect(within(box).getByRole("row", { name: /Result Stable\. Stable within the hour\./ })).toBeInTheDocument();
    // The requirement's own version is shown apart, unchanged.
    expect(screen.getAllByText(/Linked to the current wording \(version 1\)/)).toHaveLength(2);
    expect(sent).toBeNull();
    await user.click(within(box).getByRole("button", { name: "Use version 2 for these links" }));
    await waitFor(() => expect(sent).toEqual({ reviewed_revision: 2, decision: "refresh", requirement_ids: ["r-1", "r-3"] }));
    await waitFor(() => expect(screen.queryByText(/The story changed since you linked it/)).toBeNull());
  });
});
