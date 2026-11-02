import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const signInAsNurse = () =>
  server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));

describe("Dashboard and interviews follow the user's career", () => {
  it("shows a nurse their interview-question progress, not coding stats", async () => {
    signInAsNurse();
    renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByText("REGISTERED NURSE INTERVIEW PRACTICE")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ada's progress" })).toBeInTheDocument();
    const summary = screen.getByRole("region", { name: "Summary" });
    expect(within(summary).getByText("of 300 questions")).toBeInTheDocument();
    expect(screen.queryByText(/problems$/)).not.toBeInTheDocument();
    // Up next: unanswered questions from the nurse's own library.
    const next = await screen.findByRole("link", { name: /What good patient assessment looks like/ });
    expect(next).toHaveAttribute("href", "/careers/registered-nurse/questions/e-good-0");
    expect(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Interview" })).toBeInTheDocument();
  });

  it("keeps the coding dashboard for software engineers", async () => {
    renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByText("Ada's progress")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Summary" })).getByText("Solved")).toBeInTheDocument();
  });

  it("runs a nurse's mock interview from their own questions and summarises it", async () => {
    signInAsNurse();
    const { user } = renderApp("/interviews", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start interview" }));

    // Interview order: what you know comes before "tell me about a time".
    expect(await screen.findByRole("heading", { name: "What good patient assessment looks like" })).toBeInTheDocument();
    expect(screen.getByText(/QUESTION 1 OF 2/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your answer"), "Good assessment means checking vitals and listening.");
    await user.click(screen.getByRole("button", { name: "Next question" }));

    expect(await screen.findByRole("heading", { name: "A time patient assessment mattered" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Skip" }));

    expect(await screen.findByRole("heading", { name: "Registered Nurse interview results" })).toBeInTheDocument();
    expect(screen.getByText("Average score 92/100 across 1 of 2 answers.")).toBeInTheDocument();
    expect(screen.getByText("Skipped")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Work on next" })).toBeInTheDocument();
  });

  it("offers software engineers a question round next to the coding interview", async () => {
    const { user } = renderApp("/interviews", { signedIn: true });
    await user.click(await screen.findByRole("link", { name: /Start a question round/ }));
    expect(await screen.findByRole("heading", { name: "Software Engineer interview" })).toBeInTheDocument();
  });
});
