import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Reflection } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const URL = "/applications/a1/events/e1/reflection";
const R = `${API}/api/v1/me/applications/a1/events/e1/reflection`;
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: "registered-nurse" } }))));

function reflection(over: Partial<Reflection> = {}): Reflection {
  return {
    event_id: "e1", application_id: "a1", application_archived: false, role_title: "Ward nurse", employer: "Mercy General", stage: "interviewing",
    event_title: "Panel interview", event_on: "2026-11-12", questions: [], topics: [], clear: "", difficult: "", observations: [], follow_ups: "",
    practice: [], story_ids: [], missing_stories: 0, outcome: "unknown", outcome_history: [], revision: 0, saved: false, updated_at: null, warnings: [], actions: [], ...over,
  };
}

function setup(first = reflection()) {
  asNurse();
  localStorage.clear();
  server.use(
    http.get(R, () => HttpResponse.json(first)),
    http.get(`${API}/api/v1/me/stories`, () => HttpResponse.json([])),
  );
}

describe("reflecting on a real interview", () => {
  it("saves an incomplete reflection, keeping observations apart from interpretations", async () => {
    setup();
    let body: Record<string, unknown> | null = null;
    server.use(http.put(R, async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(reflection({ ...(body as Partial<Reflection>), revision: 1, saved: true, updated_at: "2026-11-12T15:00:00Z" }));
    }));
    const { user } = renderApp(URL, { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Reflect on Panel interview" })).toBeInTheDocument();
    expect(screen.getByText(/Nothing here is sent to an AI model or to anyone else/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Questions you were asked/), "A time patient assessment mattered");
    await user.type(screen.getByLabelText("Add an observation"), "They asked for another example");
    await user.click(screen.getByRole("button", { name: "Add observation" }));
    await user.type(screen.getByLabelText("Add an observation"), "They didn't like me");
    await user.click(screen.getByRole("radio", { name: "What I think it meant" }));
    await user.click(screen.getByRole("button", { name: "Add observation" }));
    await user.click(screen.getByRole("button", { name: "Save reflection" }));
    expect(await screen.findByText("Saved. Only you can see it.")).toBeInTheDocument();
    expect(body).toMatchObject({
      questions: ["A time patient assessment mattered"], clear: "", expected_revision: 0,
      observations: [{ text: "They asked for another example", kind: "observed" }, { text: "They didn't like me", kind: "interpretation" }],
    });
  });

  it("keeps unsaved words on this device when a save fails, and offers them back after a reload", async () => {
    setup();
    server.use(http.put(R, () => HttpResponse.json({ error: { code: "internal", message: "Something went wrong." } }, { status: 500 })));
    const first = renderApp(URL, { signedIn: true });
    await first.user.type(await screen.findByLabelText("What was difficult"), "The medication error question");
    await first.user.click(screen.getByRole("button", { name: "Save reflection" }));
    expect(await screen.findByText("Something went wrong.")).toBeInTheDocument();
    expect(screen.getByLabelText("What was difficult")).toHaveValue("The medication error question");
    first.unmount();
    const second = renderApp(URL, { signedIn: true });
    await second.user.click(await screen.findByRole("button", { name: "Restore them" }));
    expect(screen.getByLabelText("What was difficult")).toHaveValue("The medication error question");
  });

  it("suggests steps without applying them, accepts one once, and shows a gap honestly", async () => {
    const saved = reflection({ saved: true, revision: 1, topics: ["patient assessment", "quantum accounting"] });
    setup(saved);
    let accepts = 0;
    const withActions = (accepted = false): Reflection => ({
      ...saved,
      actions: [
        { id: "x1", kind: "practice", title: "Practise: A time patient assessment mattered", detail: "From your reflection (topic): “patient assessment”.", ref: "registered-nurse/e-time-0", href: "/careers/registered-nurse/questions/e-time-0", status: accepted ? "accepted" : "suggested", targets: ["notebook", "schedule", "saved"], target: accepted ? "saved" : null, applied_ref: accepted ? "registered-nurse/e-time-0" : null },
        { id: "x2", kind: "gap", title: "No practice here yet for “quantum accounting”", detail: "CodeCoach has nothing that covers this, so no lesson is suggested.", ref: null, href: null, status: "suggested", targets: ["notebook"], target: null, applied_ref: null },
      ],
    });
    server.use(
      http.post(`${R}/suggestions`, () => HttpResponse.json(withActions())),
      http.post(`${R}/actions/x1/accept`, () => { accepts += 1; return HttpResponse.json(withActions(true)); }),
    );
    const { user } = renderApp(URL, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Suggest next steps" }));
    const steps = await screen.findByRole("region", { name: "Next steps" });
    expect(within(steps).getByText(/Nothing is added until you choose where it goes/)).toBeInTheDocument();
    const gap = within(steps).getByText("No practice here yet for “quantum accounting”").closest("li")!;
    expect(within(gap).queryByRole("button", { name: "Add to Saved" })).not.toBeInTheDocument();
    const practice = within(steps).getByRole("link", { name: "Practise: A time patient assessment mattered" }).closest("li")!;
    await user.click(within(practice).getByRole("button", { name: "Add to Saved" }));
    expect(await within(steps).findByText(/Added to Saved\./)).toBeInTheDocument();
    expect(within(practice).queryByRole("button", { name: "Add to Saved" })).not.toBeInTheDocument(); // can't be added twice from here
    expect(accepts).toBe(1);
  });

  it("records an outcome and moves the application only when asked; archived applications still open", async () => {
    setup(reflection({ saved: true, revision: 1, application_archived: true }));
    let sent: Record<string, unknown> | null = null;
    server.use(http.put(`${R}/outcome`, async ({ request }) => {
      sent = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(reflection({ saved: true, revision: 1, application_archived: true, outcome: "offer", outcome_history: [{ outcome: "offer", at: "2026-11-20T10:00:00Z", applied_to_application: true }] }));
    }));
    const { user } = renderApp(URL, { signedIn: true });
    expect(await screen.findByText(/This application is archived\. Your reflection stays here\./)).toBeInTheDocument();
    const section = screen.getByRole("region", { name: "What happened next" });
    await user.selectOptions(within(section).getByRole("combobox", { name: /^Outcome/ }), "awaiting");
    expect(within(section).queryByRole("checkbox")).not.toBeInTheDocument(); // waiting never moves the application
    await user.selectOptions(within(section).getByRole("combobox", { name: /^Outcome/ }), "offer");
    await user.click(within(section).getByRole("checkbox", { name: /Also move the application to “Offer”/ }));
    await user.click(within(section).getByRole("button", { name: "Save outcome" }));
    await waitFor(() => expect(sent).toEqual({ outcome: "offer", update_application: true }));
    expect(await within(section).findByText(/Offer \(the application was updated\)/)).toBeInTheDocument();
  });

  it("says exactly what an outcome changed, including when the application was already there", async () => {
    setup(reflection({ saved: true, revision: 1, stage: "offer" }));
    const history = [{ outcome: "offer" as const, at: "2026-11-20T10:00:00Z", applied_to_application: false }];
    server.use(http.put(`${R}/outcome`, () => HttpResponse.json(reflection({ saved: true, revision: 1, stage: "offer", outcome: "offer", outcome_history: history }))));
    const { user } = renderApp(URL, { signedIn: true });
    const section = await screen.findByRole("region", { name: "What happened next" });
    await user.selectOptions(within(section).getByRole("combobox", { name: /^Outcome/ }), "offer");
    await user.click(within(section).getByRole("checkbox", { name: /Also move the application to “Offer”/ }));
    await user.click(within(section).getByRole("button", { name: "Save outcome" }));
    expect(await within(section).findByText("Outcome saved. The application was already at “Offer”, so it wasn't moved.")).toBeInTheDocument();
  });

  it("a failed outcome save says nothing was saved", async () => {
    setup(reflection({ saved: true, revision: 1 }));
    server.use(http.put(`${R}/outcome`, () => HttpResponse.json({ error: { code: "internal_error", message: "Something went wrong on our side.", request_id: "r" } }, { status: 500 })));
    const { user } = renderApp(URL, { signedIn: true });
    const section = await screen.findByRole("region", { name: "What happened next" });
    await user.selectOptions(within(section).getByRole("combobox", { name: /^Outcome/ }), "not_selected");
    await user.click(within(section).getByRole("checkbox", { name: /Also move the application/ }));
    await user.click(within(section).getByRole("button", { name: "Save outcome" }));
    expect(await screen.findByText(/Something went wrong on our side/)).toBeInTheDocument();
    expect(within(section).queryByText(/Outcome saved/)).toBeNull();
  });

  it("a removed note is shown as removed, not offered again; a deleted linked story is explained", async () => {
    const accepted = { id: "x1", kind: "note" as const, title: "Send references", detail: "By Friday", ref: null, href: null, status: "accepted" as const,
      targets: ["notebook" as const], target: "notebook" as const, applied_ref: "n-1", applied_available: false };
    setup(reflection({ saved: true, revision: 1, actions: [accepted], missing_stories: 1 }));
    renderApp(URL, { signedIn: true });
    const steps = await screen.findByRole("region", { name: "Next steps" });
    expect(within(steps).getByText(/You added this to your notebook, and deleted that note since/)).toBeInTheDocument();
    expect(within(steps).queryByRole("link", { name: "Open the note" })).toBeNull();
    expect(within(steps).queryByRole("button", { name: "Add to notebook" })).toBeNull();
    expect(screen.getByText(/A story you linked was deleted from your story bank since/)).toBeInTheDocument();
  });

  it("after a conflict, discarding loads the saved version", async () => {
    setup(reflection({ saved: true, revision: 1, clear: "Old" }));
    server.use(
      http.put(R, () => HttpResponse.json({ error: { code: "stale_revision", message: "Saved elsewhere", request_id: "r", details: { current_revision: 2 } } }, { status: 409 })),
    );
    const { user } = renderApp(URL, { signedIn: true });
    const clear = await screen.findByLabelText("What felt clear");
    await user.type(clear, " and mine");
    server.use(http.get(R, () => HttpResponse.json(reflection({ saved: true, revision: 2, clear: "From the other tab" }))));
    await user.click(screen.getByRole("button", { name: "Save reflection" }));
    const conflict = await screen.findByRole("region", { name: "Edit conflict" });
    // Both versions of the part that differs, under the page's own label.
    expect(within(conflict).getAllByText("What felt clear")).toHaveLength(2);
    expect(within(conflict).getByText("Old and mine")).toBeInTheDocument();
    expect(within(conflict).getByText("From the other tab")).toBeInTheDocument();
    await user.click(within(conflict).getByRole("button", { name: "Use the saved version" }));
    await waitFor(() => expect(screen.getByLabelText("What felt clear")).toHaveValue("From the other tab"));
  });

  it("a linked story can be revised in its own versioned editor, which leads back here", async () => {
    setup(reflection({ saved: true, revision: 1, story_ids: ["st1"] }));
    server.use(http.get(`${API}/api/v1/me/stories`, () => HttpResponse.json([{ id: "st1", title: "Two call lights" }, { id: "st2", title: "Night handover" }])));
    renderApp(URL, { signedIn: true });
    const link = await screen.findByRole("link", { name: "Revise “Two call lights” in your story bank" });
    expect(link).toHaveAttribute("href", "/stories/st1");
    expect(screen.queryByRole("link", { name: /Revise “Night handover”/ })).toBeNull(); // only stories linked to this reflection
  });
});


describe("reflection: exact save state", () => {
  it("when this browser can't keep a copy, the page says so and offers Copy", async () => {
    setup(reflection({ saved: true, revision: 1, clear: "Old" }));
    const blocked = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
    try {
      const { user } = renderApp(URL, { signedIn: true });
      await user.type(await screen.findByLabelText("What felt clear"), " and mine");
      expect(await screen.findByText(/this browser can't keep a copy/)).toBeInTheDocument();
      expect(screen.queryByText("Unsaved changes, kept on this device")).toBeNull();
      expect(screen.getByRole("button", { name: "Copy your text" })).toBeInTheDocument();
    } finally {
      blocked.mockRestore();
    }
  });

  it("a kept copy written against an older version is compared before anything is saved over it", async () => {
    setup(reflection({ saved: true, revision: 2, clear: "Saved later on the other device" }));
    localStorage.setItem(`reflection-draft:${baseUser.id}:e1`, JSON.stringify({
      draft: { ...fromReflectionForTest(reflection({ clear: "Kept on this device" })) }, base: 1,
    }));
    const { user } = renderApp(URL, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Restore them" }));
    const conflict = await screen.findByRole("region", { name: "Edit conflict" });
    expect(within(conflict).getByText("Kept on this device")).toBeInTheDocument();
    expect(within(conflict).getByText("Saved later on the other device")).toBeInTheDocument();
  });
});

/** The editable part of a reflection, as the page keeps it on this device. */
function fromReflectionForTest(r: Reflection) {
  return { questions: r.questions, topics: r.topics, clear: r.clear, difficult: r.difficult, observations: r.observations, follow_ups: r.follow_ups, practice: r.practice, story_ids: r.story_ids };
}
