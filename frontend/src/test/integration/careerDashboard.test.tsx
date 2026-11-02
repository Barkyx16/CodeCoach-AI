import { screen, waitFor, within } from "@testing-library/react";
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

  it("starts a nurse's mock interview from their own career on the server", async () => {
    signInAsNurse();
    let body: unknown = null;
    server.use(http.post(`${API}/api/v1/interviews`, async ({ request }) => {
      body = await request.json();
      return HttpResponse.json({ error: { code: "interview_in_progress", message: "You already have an interview in progress.", request_id: "r", details: { interview_id: "round-9" } } }, { status: 409 });
    }));
    const { user } = renderApp("/interviews", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview" })).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Medium" }));
    await user.click(screen.getByRole("button", { name: "Start interview" }));
    await waitFor(() => expect(body).toEqual({ kind: "questions", track: "registered-nurse", difficulty: "medium", duration_minutes: 15 }));
    expect(await screen.findByRole("link", { name: "Resume it" })).toHaveAttribute("href", "/interviews/round-9");
  });

  it("offers software engineers a question round next to the coding interview", async () => {
    const { user } = renderApp("/interviews", { signedIn: true });
    await user.click(await screen.findByRole("link", { name: /Start a question round/ }));
    expect(await screen.findByRole("heading", { name: "Software Engineer interview" })).toBeInTheDocument();
  });
});
