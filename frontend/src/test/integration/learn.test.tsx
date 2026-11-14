import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { tokenResponse, user as baseUser } from "../fixtures";
import { learnStore } from "../learn";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));

describe("Learn mode", () => {
  it("lists the career's units with honest coverage and opens a prerequisite", async () => {
    asNurse();
    const { user, router } = renderApp("/learn", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Registered Nurse lessons" })).toBeInTheDocument();
    expect(screen.getByText(/deliberately small: units exist for Registered Nurse \(3\) and Software Engineer \(3\)/)).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Prioritizing when several patients need you" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Prioritizing when several patients need you" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("Interview education, not clinical guidance");
    const before = screen.getByRole("region", { name: "Before you start" });
    expect(within(before).getByRole("link", { name: "SBAR for handoffs and escalation" })).toHaveAttribute("href", "/learn/rn-sbar-handoff");
    expect(within(before).getByText("Not started")).toBeInTheDocument();
    // Opening the unit records "started" once; reading isn't mastery.
    await waitFor(() => expect(learnStore.events.map((e) => e.kind)).toEqual(["started"]));
    expect(router.state.location.pathname).toBe("/learn/rn-prioritization");
  });

  it("reveals guided help step by step and the solution only after a spoiler warning, never touching the draft", async () => {
    asNurse();
    const { user } = renderApp("/learn/rn-prioritization", { signedIn: true });
    const exercise = await screen.findByRole("region", { name: "Try it" });
    const draft = within(exercise).getByLabelText("Your answer");
    await user.type(draft, "My own plan");
    await user.click(within(exercise).getByRole("button", { name: "Show step 1 of 4: a question to think about" }));
    expect(within(exercise).getByText("Which could become life-threatening?")).toBeInTheDocument();
    expect(within(exercise).queryByText("ABCs first.")).not.toBeInTheDocument();
    await user.click(within(exercise).getByRole("button", { name: "Show step 2 of 4: the key concept" }));
    expect(within(exercise).getByText("ABCs first.")).toBeInTheDocument();
    await user.click(within(exercise).getByLabelText(/On my own/));
    expect(within(exercise).queryByText("The oxygen alarm comes first.")).not.toBeInTheDocument();
    await user.click(within(exercise).getByRole("button", { name: "Show solution…" }));
    const warning = within(exercise).getByRole("alertdialog", { name: "Spoiler: this shows a complete solution." });
    expect(warning).toHaveTextContent("Your draft stays exactly as it is.");
    await user.click(within(warning).getByRole("button", { name: "Show the solution" }));
    expect(within(exercise).getByText("The oxygen alarm comes first.")).toBeInTheDocument();
    expect(draft).toHaveValue("My own plan");
    // The draft survives a remount (it lives in this browser).
    expect(window.localStorage.getItem("learn-draft:u-1:rn-prioritization") ?? Object.values(window.localStorage).join()).toContain("My own plan");
  });

  it("grades the check on the server, explains mistakes, and records read and passed separately", async () => {
    asNurse();
    const { user } = renderApp("/learn/rn-prioritization", { signedIn: true });
    const next = await screen.findByRole("region", { name: "Next step" });
    expect(next).toHaveTextContent("Read the unit, then mark it read");
    await user.click(screen.getByRole("button", { name: "I've read this unit" }));
    expect(await screen.findByText(/Marked as read for version 1\. Reading on its own isn't mastery/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("region", { name: "Next step" })).toHaveTextContent("Take the comprehension check"));
    const check = screen.getByRole("region", { name: "Check yourself" });
    await user.click(within(check).getByLabelText("Labored breathing"));
    await user.click(within(check).getByLabelText("Never asking for help"));
    await user.click(within(check).getByRole("button", { name: "Check my answers" }));
    expect(await within(check).findByText(/1 of 2 right\. Read the explanations and try again/)).toBeInTheDocument();
    expect(within(check).getByText(/The answer is “Escalating appropriately”\./)).toBeInTheDocument();
    await user.click(within(check).getByLabelText("Escalating appropriately"));
    await user.click(within(check).getByRole("button", { name: "Check again" }));
    expect(await within(check).findByText(/Passed: 2 of 2 right\. This is recorded for version 1; it doesn't mark any problem solved\./)).toBeInTheDocument();
    expect(learnStore.events.map((e) => e.kind)).toEqual(["started", "read", "check_attempted", "check_attempted", "check_passed"]);
    await waitFor(() => expect(screen.getByRole("region", { name: "Next step" })).toHaveTextContent("Answer “Patient assessment under pressure”"));
    expect(screen.getByRole("region", { name: "Practice" })).toHaveTextContent("Not practised yet. It's recorded from your real answer, not from reading.");
  });

  it("shows which version you used after the unit is revised, and handles an update mid-read", async () => {
    asNurse();
    learnStore.events = [{ kind: "started", version: 1, at: "2026-11-01T09:00:00Z", detail: null }, { kind: "check_passed", version: 1, at: "2026-11-01T09:05:00Z", detail: "every answer right" }];
    learnStore.version = 2;
    const { user } = renderApp("/learn/rn-prioritization", { signedIn: true });
    expect(await screen.findByText(/You last used version 1; this is version 2\. What changed: Added a reassessment step\. Your earlier progress is kept\./)).toBeInTheDocument();
    // The page loaded version 2; if the server moves on again, recording is refused and the page says so.
    learnStore.version = 3;
    await user.click(await screen.findByRole("button", { name: "I've read this unit" }));
    expect(await screen.findByText(/This unit was updated while you had it open\./)).toBeInTheDocument();
  });

  it("states missing links honestly and shows Learn first on a related question", async () => {
    asNurse();
    const { user } = renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    const links = await screen.findByRole("region", { name: "Learn first" });
    await user.click(within(links).getByRole("link", { name: "Prioritizing when several patients need you" }));
    const sources = await screen.findByRole("region", { name: "Sources and review" });
    expect(within(sources).getByText("Clinical Judgment Measurement Model (NCSBN)").tagName).toBe("SPAN"); // no guessed link
    expect(within(sources).getByText("In this repository")).toBeInTheDocument();
    expect(within(sources).getByText(/Not reviewed by a licensed nurse educator/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the question" })).toBeInTheDocument();
  });

  it("a career without units says so instead of showing another career's", async () => {
    renderApp("/learn?career=software-engineer");
    expect(await screen.findByText("No lessons for Software Engineer yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Registered Nurse (3)" })).toHaveAttribute("href", "/learn?career=registered-nurse");
  });
});
