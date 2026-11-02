import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };

describe("Career practice", () => {
  it("shows interview questions for the user's job, in difficulty tabs", async () => {
    server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
    renderApp("/problems", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview questions" })).toBeInTheDocument();
    const tabs = screen.getByRole("tablist", { name: "Difficulty" });
    expect(await within(tabs).findByRole("tab", { name: "Easy 2" })).toHaveAttribute("aria-selected", "true");
    const row = (await screen.findByText("A time patient assessment mattered")).closest("a") as HTMLElement;
    expect(row).toHaveAttribute("href", "/careers/registered-nurse/questions/e-time-0");
    expect(within(row).getByLabelText("Best score 90")).toBeInTheDocument();
    expect(within(row).getByText("Behavioral")).toBeInTheDocument();
    // No coding problems for this job, so no coding/questions switch.
    expect(screen.queryByRole("navigation", { name: "Practice type" })).not.toBeInTheDocument();
  });

  it("lets software engineers switch between coding problems and interview questions", async () => {
    const { user, router } = renderApp("/problems", { signedIn: true });
    const switcher = await screen.findByRole("navigation", { name: "Practice type" });
    expect(within(switcher).getByRole("link", { name: "Coding problems" })).toHaveAttribute("aria-current", "page");
    expect(await screen.findByText("Two Sum")).toBeInTheDocument();
    await user.click(within(switcher).getByRole("link", { name: "Interview questions" }));
    expect(router.state.location.search).toContain("view=questions");
    expect(await screen.findByRole("heading", { name: "Software Engineer interview questions" })).toBeInTheDocument();
  });

  it("changing the job saves it to the profile", async () => {
    let body: unknown = null;
    server.use(http.patch(`${API}/api/v1/auth/me`, async ({ request }) => {
      body = await request.json();
      return HttpResponse.json(nurse);
    }));
    const { user } = renderApp("/problems", { signedIn: true });
    const select = await screen.findByLabelText("Practicing for");
    await waitFor(() => expect(select).toBeEnabled());
    await user.selectOptions(select, "registered-nurse");
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview questions" })).toBeInTheDocument();
    expect(body).toEqual({ career_track: "registered-nurse" });
  });

  it("signed-out visitors can browse any job's questions from the URL", async () => {
    renderApp("/problems?career=registered-nurse");
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview questions" })).toBeInTheDocument();
    expect(screen.getByText("Sign in or try as a guest to get feedback")).toBeInTheDocument();
  });

  it("answers a question and shows rubric feedback", async () => {
    let sent: unknown = null;
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, async ({ request }) => {
      sent = await request.json();
      const { nurseAnswer } = await import("../fixtures");
      return HttpResponse.json(nurseAnswer, { status: 201 });
    }));
    const { user } = renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Patient assessment under pressure", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("Use the STAR method.")).toBeInTheDocument();
    const box = screen.getByLabelText("Your answer");
    expect(screen.getByRole("button", { name: "Get feedback" })).toBeDisabled();
    await user.type(box, "Last winter I handled a deteriorating patient.");
    expect(screen.getByText(/7 words/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    const feedback = await screen.findByRole("region", { name: "Feedback" });
    expect(within(feedback).getByLabelText("Score 92 out of 100, Strong")).toBeInTheDocument();
    expect(within(feedback).getByText("Finish with what happened.")).toBeInTheDocument(); // advice for the missed point
    expect(within(feedback).getByText("Situation: what made it high-pressure.")).toBeInTheDocument();
    expect(sent).toEqual({ answer: "Last winter I handled a deteriorating patient." });
  });

  it("asks signed-out visitors to sign in or start a guest session for feedback", async () => {
    let guestBody: unknown = null;
    server.use(http.post(`${API}/api/v1/auth/guest`, async ({ request }) => {
      guestBody = await request.json();
      return HttpResponse.json(tokenResponse({ user: { ...nurse, is_guest: true, email: null } }), { status: 201 });
    }));
    const { user } = renderApp("/careers/registered-nurse/questions/e-good-0");
    expect(await within(await screen.findByRole("main")).findByRole("link", { name: "Sign in" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try as a guest" }));
    expect(await screen.findByRole("button", { name: "Get feedback" })).toBeInTheDocument();
    expect(guestBody).toEqual({ career_track: "registered-nurse" });
  });

  it("saves the career from Settings", async () => {
    let body: unknown = null;
    server.use(http.patch(`${API}/api/v1/auth/me`, async ({ request }) => {
      body = await request.json();
      return HttpResponse.json({ ...baseUser, career_track: "barista" });
    }));
    const { user } = renderApp("/settings", { signedIn: true });
    const form = within(await screen.findByRole("form", { name: "Career" }));
    const select = form.getByLabelText("Job you're preparing for");
    await waitFor(() => expect(select).toBeEnabled());
    expect(form.getByRole("button", { name: "Save career" })).toBeDisabled(); // nothing changed yet
    await user.selectOptions(select, "barista");
    await user.click(form.getByRole("button", { name: "Save career" }));
    expect(await form.findByText(/Your practice questions now match this job/)).toBeInTheDocument();
    expect(body).toEqual({ career_track: "barista" });
  });

  it("requires a job at sign-up and sends it", async () => {
    let body: Record<string, unknown> = {};
    server.use(http.post(`${API}/api/v1/auth/register`, async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(tokenResponse(), { status: 201 });
    }));
    const { user } = renderApp("/register");
    await user.type(await screen.findByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    const create = within(screen.getByRole("main")).getByRole("button", { name: "Create account" });
    expect(create).toBeDisabled();
    await user.selectOptions(await screen.findByLabelText("Job you're preparing for"), "barista");
    await user.click(create);
    await waitFor(() => expect(body.career_track).toBe("barista"));
  });
});
