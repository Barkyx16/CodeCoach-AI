/**
 * The portfolio demo's entry (Volume 7, prompt 10): what the server can really do, fictional
 * sample learners with labelled example answers, and a per-visitor session that starts on a
 * question with a way back. Off a demo server, it says so; on one, accounts aren't offered.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { DemoOut } from "@/api/types";

import { executionStatus, nurseQuestions, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const LABEL = "Example answer, written for this demo by a fictional learner. The score is CodeCoach's built-in grader's, from when the demo was set up.";
const DEMO: DemoOut = {
  personas: [
    {
      key: "nurse", name: "Sam Rivera", career_track: "registered-nurse", career_title: "Registered Nurse",
      summary: "A fictional registered nurse.", start_question_id: nurseQuestions[0]!.id, start_question_title: nurseQuestions[0]!.title,
      problem_slug: null,
      examples: [
        { question_id: "e-time-0", question_title: "A time patient assessment mattered", answer: "Last winter, on a night shift…", score: 86,
          rating: "Strong", summary: "A clear story with a result.", answered_at: "2026-01-13T09:00:00Z", label: LABEL },
        { question_id: "e-good-0", question_title: "What good patient assessment looks like", answer: "Checking the patient properly.", score: 31,
          rating: "Needs work", summary: "Too general.", answered_at: "2026-01-14T09:00:00Z", label: LABEL },
      ],
    },
    {
      key: "engineer", name: "Alex Chen", career_track: "software-engineer", career_title: "Software Engineer",
      summary: "A fictional software engineer.", start_question_id: "e-steps-0", start_question_title: "Your approach to debugging",
      problem_slug: "two-sum", examples: [],
    },
  ],
  notes: ["Everyone here is fictional. Your own session is a guest session that only you can see."],
};

function demoServer({ judge = "not_configured" as "ready" | "not_configured", ai = "offline" } = {}) {
  let guestBody: unknown = null;
  server.use(
    http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({
      execution_enabled: judge === "ready", ai_provider: ai, execution: executionStatus(judge), guest_retention_days: 30,
      emails_delivered: false, answer_request_keys: true, demo_mode: true,
    })),
    http.get(`${API}/api/v1/demo`, () => HttpResponse.json(DEMO)),
    http.post(`${API}/api/v1/auth/guest`, async ({ request }) => {
      guestBody = await request.json();
      return HttpResponse.json(tokenResponse({ user: { ...baseUser, email: null, is_guest: true, display_name: "Demo visitor", career_track: "registered-nurse" } }), { status: 201 });
    }),
  );
  return { get guestBody() { return guestBody; } };
}

it("says what this server can do, honestly, and shows the fictional examples labelled as examples", async () => {
  demoServer();
  renderApp("/demo");
  expect(await screen.findByRole("heading", { name: "Try CodeCoach with a sample learner", level: 1 })).toBeInTheDocument();
  const caps = screen.getByRole("region", { name: "What this demo server can do right now" });
  expect(caps).toHaveTextContent("isn't connected to a code judge"); // the server's own message, not a claim it runs code
  expect(caps).toHaveTextContent("No AI service is called");
  expect(caps).toHaveTextContent(/Email\s*None is sent/);
  expect(caps).toHaveTextContent("This browser has no speech features"); // jsdom has none
  const sam = await screen.findByRole("region", { name: /Sam Rivera/ });
  expect(sam).toHaveTextContent("(fictional) · Registered Nurse");
  await screen.findByText("Sam Rivera's example answers (2)");
  const examples = within(sam).getAllByRole("article");
  expect(examples).toHaveLength(2);
  for (const e of examples) expect(e).toHaveTextContent(`Example. ${LABEL}`);
  expect(examples[0]).toHaveTextContent("Score 86/100 · Strong");
});

it("a live judge is described as running code, and a live AI provider as having a limit", async () => {
  demoServer({ judge: "ready", ai: "anthropic" });
  renderApp("/demo");
  const caps = await screen.findByRole("region", { name: "What this demo server can do right now" });
  expect(caps).toHaveTextContent("Runs and judges your code in an isolated sandbox.");
  expect(caps).toHaveTextContent("with a daily limit per visitor");
});

it("starting gives the visitor their own guest session on the chosen career, with a way back", async () => {
  const srv = demoServer();
  const { user, router } = renderApp("/demo");
  await user.click(await screen.findByRole("button", { name: "Start a demo session as a registered nurse" }));
  await waitFor(() => expect(router.state.location.pathname).toBe(`/careers/registered-nurse/questions/${nurseQuestions[0]!.id}`));
  expect(srv.guestBody).toEqual({ display_name: "Demo visitor", career_track: "registered-nurse" });
  expect(await screen.findByRole("link", { name: "Back to the demo" })).toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Back to the demo" }));
  // Back on the demo: the things to try, for this visitor's career.
  const steps = await screen.findByRole("heading", { name: "Things to try (about ten minutes)" });
  const card = steps.closest(".card") as HTMLElement;
  expect(within(card).getByRole("link", { name: `Answer “${nurseQuestions[0]!.title}”` })).toHaveAttribute(
    "href", `/careers/registered-nurse/questions/${nurseQuestions[0]!.id}`);
  expect(within(card).getByText(/Leave and come back:/)).toBeInTheDocument();
});

it("off a demo server, the page says so instead of pretending", async () => {
  renderApp("/demo");
  expect(await screen.findByRole("heading", { name: "This server isn't running the demo", level: 1 })).toBeInTheDocument();
});

it("on a demo server, accounts aren't offered and the start page points to the demo", async () => {
  demoServer();
  const { user, router } = renderApp("/register");
  expect(await screen.findByRole("heading", { name: "Accounts can't be created on this demo" })).toBeInTheDocument();
  expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Go to the guided demo" }));
  expect(router.state.location.pathname).toBe("/demo");
  await router.navigate("/");
  expect(await screen.findByRole("note")).toHaveTextContent("This is a demo with fictional data.");
  // The header offers the demo, not accounts this server can't create or sign in to.
  const header = screen.getByRole("banner");
  expect(within(header).getByRole("link", { name: "Guided demo" })).toHaveAttribute("href", "/demo");
  expect(within(header).queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
  expect(within(header).queryByRole("link", { name: "Create account" })).not.toBeInTheDocument();
});
