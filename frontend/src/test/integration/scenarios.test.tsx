import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ScenarioAttempt } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { scenarioStore, scenarioSummary } from "../scenarios";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));

describe("Branching scenarios", () => {
  it("briefs before starting: role, goal, estimate, scope, how choices work", async () => {
    asNurse();
    const { user, router } = renderApp("/scenarios", { signedIn: true });
    expect(await screen.findByText(/Scenarios are new and few/)).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Two call lights at once" }));
    expect(await screen.findByText("Medical-surgical nurse")).toBeInTheDocument();
    expect(screen.getByText("About 7 minutes (the author's estimate)")).toBeInTheDocument();
    expect(screen.getByText("Fictional, not clinically validated.")).toBeInTheDocument();
    expect(screen.getAllByText("Not clinically validated").length).toBeGreaterThan(0);
    expect(screen.getByText(/Each choice is final for this attempt/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start the scenario" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/scenarios/attempts/att-1"));
  });

  it("plays a path, shows the decision rule for each choice, and debriefs that exact path", async () => {
    asNurse();
    const { user, router } = renderApp("/scenarios/rn-two-patients", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Start the scenario" }));
    const current = () => screen.getByRole("region", { name: screen.getByRole("heading", { level: 2, name: /Start of shift|Who first\?|Make the call|Later/ }).textContent! });
    await screen.findByRole("heading", { level: 2, name: "Start of shift" });
    await user.click(within(current()).getByRole("button", { name: "Continue" }));
    const choiceHeading = await screen.findByRole("heading", { level: 2, name: "Who first?" });
    await waitFor(() => expect(choiceHeading).toHaveFocus());
    const confirm = screen.getByRole("button", { name: "Confirm this decision" });
    expect(confirm).toBeDisabled();
    expect(screen.getByText("Your choice is final for this attempt. You can try another approach afterwards.")).toBeInTheDocument();
    await user.click(screen.getByLabelText("Bed 7 (pain)"));
    await user.click(confirm);
    const history = await screen.findByRole("list", { name: "What has happened so far" });
    expect(await within(history).findByText("Bed 7 (pain)", { exact: false })).toBeInTheDocument();
    expect(within(history).getByText("Risky")).toBeInTheDocument();
    expect(within(history).getByText(/Breathing should come first\./)).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    const debrief = await screen.findByRole("region", { name: "Debrief" });
    await waitFor(() => expect(screen.getByRole("heading", { name: "Debrief" })).toHaveFocus());
    expect(debrief).toHaveTextContent("Help arrived late (simulated)");
    expect(debrief).toHaveTextContent("Outcomes are simulated consequences of a fictional case.");
    expect(debrief).toHaveTextContent("No AI commentary was generated.");
    expect(within(debrief).getByRole("link", { name: "Who first?" })).toHaveAttribute("href", "#step-1");
    expect(within(debrief).getByText("Start of shift")).toBeInTheDocument();
    // A separate exploration attempt; the original stays.
    await user.click(within(debrief).getByRole("button", { name: "Try another approach" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/scenarios/attempts/att-2"));
    expect(await screen.findByText("Exploration: a separate attempt; your original is kept")).toBeInTheDocument();
    expect(scenarioStore.attempts.find((a) => a.id === "att-1")!.status).toBe("completed");
  });

  it("explains a stale step and reloads to the real position", async () => {
    asNurse();
    const { user } = renderApp("/scenarios/rn-two-patients", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Start the scenario" }));
    await screen.findByRole("heading", { level: 2, name: "Start of shift" });
    // Another tab moves the attempt on.
    (scenarioStore.attempts[0] as unknown as { node: string }).node = "who";
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("That step isn't the current one. Reload to see where you are.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 2, name: "Who first?" })).toBeInTheDocument();
  });

  it("keeps a retired attempt readable but not continuable", async () => {
    asNurse();
    const { user } = renderApp("/scenarios/rn-two-patients", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Start the scenario" }));
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    await screen.findByRole("heading", { level: 2, name: "Who first?" });
    scenarioStore.retire = true;
    await user.click(screen.getByLabelText("Bed 3 (breathing)"));
    await user.click(screen.getByRole("button", { name: "Confirm this decision" }));
    expect(await screen.findByText(/This scenario has been updated to version 2\. This attempt \(version 1\) is kept as it was and can't be continued/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm this decision" })).not.toBeInTheDocument();
  });

  const finished = (over: Partial<ScenarioAttempt>): ScenarioAttempt => ({
    id: "att-9", scenario: scenarioSummary, version: 1, mode: "assessed", parent_id: null, status: "completed", retired: false, current: null, steps: [],
    created_at: "2026-11-18T07:00:00Z", updated_at: "2026-11-18T07:05:00Z", completed_at: "2026-11-18T07:05:00Z",
    debrief: { outcome: "Escalation delayed (simulated)", ending_title: "Later", ending_text: "", summary: "Debrief text.", path: ["Start of shift", "Who first?", "Later"],
      decisions: [], strengths: [], written: [], references: [], feedback_source: "Authored rules.", disclaimer: "Simulated." },
    ...over,
  });

  it("sets a finished run beside the one before by the contract, linking to it (Volume 20, prompt 2)", async () => {
    asNurse();
    const EXPLAIN = "Partly comparable: the runs took different paths: 1 of the decisions were the same, of 3 in the earlier run and 3 in this one; set the decisions side by side, not the counts. (Comparison rules v1)";
    server.use(http.get(`${API}/api/v1/me/scenario-attempts/att-9`, () => HttpResponse.json(finished({
      compared: {
        previous: { id: "att-8", created_at: "2026-11-18T06:00:00Z", result: "2 strong, 0 acceptable, 0 risky · ended: Escalated promptly (simulated)" },
        result: "0 strong, 0 acceptable, 2 risky · ended: Escalation delayed (simulated)",
        comparison: { against: "att-8", outcome: "partially_comparable", scores_comparable: false, points_comparable: true, reasons: [{ rule: "path", kind: "partial_text", text: "the runs took different paths" }], explanation: EXPLAIN, contract_version: 1 },
      },
      not_compared: null,
    }))));
    renderApp("/scenarios/attempts/att-9", { signedIn: true });
    const debrief = await screen.findByRole("region", { name: "Debrief" });
    const compared = within(debrief).getByRole("region", { name: "Compared with your previous attempt" });
    expect(compared).toHaveTextContent("2 strong, 0 acceptable, 0 risky · ended: Escalated promptly (simulated)");
    expect(compared).toHaveTextContent("This one: 0 strong, 0 acceptable, 2 risky · ended: Escalation delayed (simulated)");
    expect(within(compared).getByText(EXPLAIN)).toBeInTheDocument();
    expect(within(compared).getByRole("link", { name: "Open that run" })).toHaveAttribute("href", "/scenarios/attempts/att-8");
  });

  it("says why a finished run isn't compared, and nothing while it's in progress", async () => {
    asNurse();
    server.use(http.get(`${API}/api/v1/me/scenario-attempts/att-9`, () => HttpResponse.json(finished({ compared: null, not_compared: "Not compared: the first finished run of this scenario" }))));
    renderApp("/scenarios/attempts/att-9", { signedIn: true });
    const debrief = await screen.findByRole("region", { name: "Debrief" });
    expect(within(debrief).getByText("Not compared: the first finished run of this scenario")).toBeInTheDocument();
    expect(within(debrief).queryByRole("region", { name: "Compared with your previous attempt" })).not.toBeInTheDocument();
  });
});
