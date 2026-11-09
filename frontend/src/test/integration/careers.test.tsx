import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { tokenResponse, user as baseUser } from "../fixtures";
import { chooseCareer } from "../careerPicker";
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

  it("choosing another job in the library shows it without changing the profile (Settings does that)", async () => {
    let body: unknown = null;
    server.use(http.patch(`${API}/api/v1/auth/me`, async ({ request }) => {
      body = await request.json();
      return HttpResponse.json(nurse);
    }));
    const { user, router } = renderApp("/problems", { signedIn: true });
    await chooseCareer(user, await screen.findByLabelText("Show practice for"), "registered-nurse");
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview questions" })).toBeInTheDocument();
    expect(router.state.location.search).toBe("?career=registered-nurse");
    expect(body).toBeNull();
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
    await chooseCareer(user, select, "barista");
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
    await chooseCareer(user, await screen.findByLabelText("Job you're preparing for"), "barista");
    await user.click(create);
    await waitFor(() => expect(body.career_track).toBe("barista"));
  });
});

describe("Answering with the keyboard", () => {
  const QUESTION = "/careers/registered-nurse/questions/m-pressure-0";

  it("submits with the keyboard and moves focus to the feedback, so it isn't lost", async () => {
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, async () => {
      const { nurseAnswer } = await import("../fixtures");
      return HttpResponse.json(nurseAnswer, { status: 201 });
    }));
    const { user } = renderApp(QUESTION, { signedIn: true });
    const box = await screen.findByLabelText("Your answer");
    await user.click(box);
    // Dictation inserts line breaks: Enter in the answer box is a new line, never a submission.
    await user.keyboard("Last winter I handled a deteriorating patient.{Enter}I called the doctor.");
    expect(screen.queryByRole("region", { name: "Feedback" })).not.toBeInTheDocument();
    expect(box).toHaveValue("Last winter I handled a deteriorating patient.\nI called the doctor.");
    await user.tab(); // to "Get feedback"
    expect(screen.getByRole("button", { name: "Get feedback" })).toHaveFocus();
    await user.keyboard("{Enter}");
    const feedback = await screen.findByRole("region", { name: "Feedback" });
    // The emptied box disables the button; focus goes to the feedback heading instead of the page.
    await waitFor(() => expect(within(feedback).getByRole("heading", { name: "Feedback" })).toHaveFocus());
  });

  it("with reflection first, focus goes to the reflection step and then to the feedback", async () => {
    window.localStorage.setItem("codecoach.reflect-first", "on");
    server.use(
      http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, async () => {
        const { nurseAnswer } = await import("../fixtures");
        return HttpResponse.json(nurseAnswer, { status: 201 });
      }),
      http.put(`${API}/api/v1/me/answers/:id/self-review`, () => HttpResponse.json({})),
    );
    const { user } = renderApp(QUESTION, { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Last winter I handled a deteriorating patient.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Before you read the feedback" })).toHaveFocus());
    await user.click(screen.getByRole("button", { name: "Skip and show feedback" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Feedback" })).toHaveFocus());
  });

  it("keeps the answer and the focus when sending fails, and sends it again", async () => {
    let tries = 0;
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, async () => {
      tries += 1;
      if (tries === 1) {
        return HttpResponse.json({ error: { code: "unavailable", message: "The server is busy. Try again.", request_id: "r", details: null } }, { status: 503 });
      }
      const { nurseAnswer } = await import("../fixtures");
      return HttpResponse.json(nurseAnswer, { status: 201 });
    }));
    const { user } = renderApp(QUESTION, { signedIn: true });
    const box = await screen.findByLabelText("Your answer");
    await user.type(box, "Last winter I handled a deteriorating patient.");
    await user.tab();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("The server is busy. Try again.");
    expect(box).toHaveValue("Last winter I handled a deteriorating patient.");
    expect(box).toHaveAccessibleDescription(/words.*The server is busy/);
    const send = screen.getByRole("button", { name: "Get feedback" });
    expect(send).toHaveFocus(); // still where the learner was
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("region", { name: "Feedback" })).toBeInTheDocument();
  });
});

describe("Which answer owns the feedback on screen", () => {
  // The page that sent an answer shows its feedback. Moving to another question starts that
  // question afresh: an earlier question's feedback, even one still on its way, never appears
  // there, and that question's own draft is left alone. (The earlier answer is still saved; it is
  // listed under its own question and in History.)
  const A = "/careers/registered-nurse/questions/m-pressure-0";
  const B = "/careers/registered-nurse/questions/e-good-0";

  it("an earlier question's feedback isn't shown on the next question", async () => {
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, async () => {
      const { nurseAnswer } = await import("../fixtures");
      return HttpResponse.json(nurseAnswer, { status: 201 });
    }));
    const { user, router } = renderApp(A, { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Last winter I handled a deteriorating patient.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    expect(await screen.findByRole("region", { name: "Feedback" })).toBeInTheDocument();
    await act(() => router.navigate(B));
    expect(await screen.findByLabelText("Your answer")).toHaveValue("");
    expect(screen.queryByRole("region", { name: "Feedback" })).not.toBeInTheDocument();
  });

  it("a slow answer that finishes after moving on doesn't land on the next question or clear its draft", async () => {
    let release!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    let sent = false;
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, async () => {
      sent = true;
      await held;
      const { nurseAnswer } = await import("../fixtures");
      return HttpResponse.json(nurseAnswer, { status: 201 });
    }));
    const { user, router } = renderApp(A, { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Last winter I handled a deteriorating patient.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await waitFor(() => expect(sent).toBe(true));
    await act(() => router.navigate(B));
    const box = await screen.findByLabelText("Your answer");
    await user.type(box, "My answer to the second question.");
    await act(async () => { release(); await held; });
    await waitFor(() => expect(window.localStorage.length).toBeGreaterThan(0));
    expect(screen.queryByRole("region", { name: "Feedback" })).not.toBeInTheDocument();
    expect(box).toHaveValue("My answer to the second question.");
  });

  it("pressing twice quickly sends the answer once", async () => {
    let posts = 0;
    let release!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    server.use(http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, async () => {
      posts += 1;
      await held;
      const { nurseAnswer } = await import("../fixtures");
      return HttpResponse.json(nurseAnswer, { status: 201 });
    }));
    const { user } = renderApp(A, { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Last winter I handled a deteriorating patient.");
    const send = screen.getByRole("button", { name: "Get feedback" });
    await user.click(send);
    await waitFor(() => expect(posts).toBe(1));
    await user.click(send); // still busy: ignored
    await user.keyboard("{Enter}");
    release();
    expect(await screen.findByRole("region", { name: "Feedback" })).toBeInTheDocument();
    expect(posts).toBe(1);
  });
});
