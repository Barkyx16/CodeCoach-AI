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
    practice: [], story_ids: [], outcome: "unknown", outcome_history: [], revision: 0, saved: false, updated_at: null, warnings: [], actions: [], ...over,
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
});
