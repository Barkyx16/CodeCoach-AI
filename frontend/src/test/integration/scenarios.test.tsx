import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { scenarioStore } from "../scenarios";
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
});
