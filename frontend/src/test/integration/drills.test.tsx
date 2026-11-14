import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Drill, DrillAttempt } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";
import { FakeRecognition, installSpeech, uninstallSpeech } from "../speech";

const D = `${API}/api/v1/me/drills`;
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: "registered-nurse" } }))));

const intro: Drill = {
  id: "intro", title: "Introduce yourself briefly", objective: "Say who you are and why you fit, in about a minute.",
  looks_for: ["Says what you do or are working towards", "Mentions one concrete strength or experience", "Ends by connecting to this kind of role"],
  target_seconds: 60, prompt: "Introduce yourself for a registered nurse interview.", attempts: 0,
};

function attempt(over: Partial<DrillAttempt> = {}): DrillAttempt {
  return {
    id: "a1", drill_id: "intro", prompt: intro.prompt, text: "I'm a registered nurse.", source: "typed", spoken_seconds: null, rubric_version: 1, created_at: "2026-11-03T10:00:00Z",
    compared_with_previous: null,
    feedback: {
      rubric_version: 1,
      observations: [
        { point: intro.looks_for[0], present: true, detail: "Says what you do" },
        { point: intro.looks_for[1], present: false, detail: "Names a strength or experience" },
        { point: intro.looks_for[2], present: true, detail: "Connects it to the role" },
      ],
      generalities: [], measured: { words: 4, reading_estimate_seconds: 2 }, notes: ["The aim is about 60 seconds; that's a guide, not a score."],
      limitations: "Built-in rules that look for the points above in your words.",
    },
    ...over,
  };
}

function setup(attempts: DrillAttempt[] = []) {
  asNurse();
  localStorage.clear();
  server.use(
    http.get(`${D}/intro`, () => HttpResponse.json(intro)),
    http.get(`${D}/intro/attempts`, () => HttpResponse.json(attempts)),
  );
}

afterEach(() => uninstallSpeech());

describe("communication drills", () => {
  it("shows the objective and what feedback looks for, then gives typed feedback that never invents spoken time", async () => {
    setup();
    let body: Record<string, unknown> | null = null;
    server.use(http.post(`${D}/intro/attempts`, async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(attempt({ text: String(body.text) }), { status: 201 });
    }));
    const { user } = renderApp("/drills/intro", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Introduce yourself briefly" })).toBeInTheDocument();
    expect(screen.getByText("Introduce yourself for a registered nurse interview.")).toBeInTheDocument();
    expect(screen.getByText("Mentions one concrete strength or experience")).toBeInTheDocument();
    expect(screen.getByText(/Speaking needs speech recognition, which this browser doesn't offer/)).toBeInTheDocument();
    const send = screen.getByRole("button", { name: "Get feedback" });
    await user.type(screen.getByLabelText(/Answer \(check and edit/), "Hi.");
    expect(send).toBeDisabled(); // nothing to review yet
    await user.type(screen.getByLabelText(/Answer \(check and edit/), " I'm a registered nurse.");
    await user.click(send);
    const fb = await screen.findByRole("region", { name: /Feedback on your attempt/ });
    expect(within(fb).getByText("Spoken time: not measured (typed answer)")).toBeInTheDocument();
    expect(within(fb).getByText(/an estimate, not a measurement/)).toBeInTheDocument();
    expect((body as unknown as { source: string; spoken_seconds: unknown }).source).toBe("typed");
    expect((body as unknown as { spoken_seconds: unknown }).spoken_seconds).toBeNull();
  });

  it("dictates into an editable box, and a failed send keeps the words and retries as the same attempt", async () => {
    installSpeech();
    setup();
    const ids: string[] = [];
    let fail = true;
    server.use(http.post(`${D}/intro/attempts`, async ({ request }) => {
      const b = (await request.json()) as { client_request_id: string; source: string; text: string };
      ids.push(b.client_request_id);
      if (fail) return HttpResponse.json({ error: { code: "internal", message: "Something went wrong." } }, { status: 500 });
      return HttpResponse.json(attempt({ text: b.text, source: "voice" }), { status: 201 });
    }));
    const { user } = renderApp("/drills/intro", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Speak your answer" }));
    expect(screen.getByRole("button", { name: "Stop speaking" })).toBeInTheDocument();
    FakeRecognition.latest.emit(["um I'm a nurse on a medical ward", true]);
    await user.click(screen.getByRole("button", { name: "Stop speaking" }));
    FakeRecognition.latest.end();
    const box = screen.getByLabelText(/Answer \(check and edit/);
    expect(box).toHaveValue("um I'm a nurse on a medical ward");
    await user.type(box, " and I want this role.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    expect(await screen.findByText("Something went wrong.")).toBeInTheDocument();
    expect(box).toHaveValue("um I'm a nurse on a medical ward and I want this role.");
    fail = false;
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await screen.findByRole("region", { name: /Feedback on your attempt/ });
    expect(ids).toHaveLength(2);
    expect(ids[0]).toBe(ids[1]); // one attempt, however many tries it took
  });

  it("says plainly when the microphone is blocked, and typing still works", async () => {
    installSpeech();
    setup();
    const { user } = renderApp("/drills/intro", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Speak your answer" }));
    FakeRecognition.latest.fail("not-allowed");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Microphone access is blocked/);
    await user.type(screen.getByLabelText(/Answer \(check and edit/), "I'm a nurse who wants this role.");
    expect(screen.getByRole("button", { name: "Get feedback" })).toBeEnabled();
  });

  it("compares with the previous attempt, opens an attempt from the URL, and can hide delivery measurements", async () => {
    const older = attempt({ id: "a0", created_at: "2026-11-02T10:00:00Z" });
    const newer = attempt({
      id: "a1", source: "voice", spoken_seconds: 41, compared_with_previous: ["Now there: mentions one concrete strength or experience."],
      feedback: { ...attempt().feedback, measured: { words: 25, spoken_seconds: 41, reading_estimate_seconds: 10 } },
    });
    setup([newer, older]);
    const { user } = renderApp("/drills/intro?attempt=a1", { signedIn: true });
    const fb = await screen.findByRole("region", { name: /Feedback on your attempt/ });
    expect(within(fb).getByText("Now there: mentions one concrete strength or experience.")).toBeInTheDocument();
    expect(within(fb).getByText(/The microphone was on for 41 seconds, pauses included/)).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: /Show delivery measurements/ }));
    expect(within(fb).queryByText(/The microphone was on for 41 seconds/)).not.toBeInTheDocument();
    expect(within(fb).queryByText(/The aim is about 60 seconds/)).not.toBeInTheDocument();
    expect(screen.getByText("There's no time limit, and speed isn't scored.")).toBeInTheDocument();
    await waitFor(() => expect(localStorage.getItem("codecoach.drills.delivery")).toBe("off"));
  });
});
