import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Interview, RoundQuestion } from "@/api/types";

import { nurseAnswer, nurseQuestions, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";
import { FakeRecognition, finishSpeaking, installSpeech, spoken, uninstallSpeech } from "../speech";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = () => new Date().toISOString();

/** A tiny in-memory question-round server: the same rules as the backend, enough for the UI. */
function roundServer({ answerDelay }: { answerDelay?: Promise<void> } = {}) {
  const questions: RoundQuestion[] = nurseQuestions.slice(0, 2).map((q, index) => ({
    index, id: q.id, title: q.title, prompt: q.prompt, kind: q.kind, difficulty: q.difficulty as RoundQuestion["difficulty"],
    status: index === 0 ? "current" : "pending", answer: null,
  }));
  let iv: Interview = {
    id: "round-1", kind: "questions", status: "in_progress", phase: null, phase_index: 5, phase_guide: null,
    problem: null, track: "registered-nurse", career_title: "Registered Nurse", questions,
    round_summary: { answered: 0, skipped: 0, unanswered: 2, average_score: null, focus: [] },
    duration_seconds: 900, started_at: now(), deadline_at: new Date(Date.now() + 900_000).toISOString(),
    ended_at: null, seconds_remaining: 900, candidate_turns_remaining: 30, provider: "built-in (offline)",
    turns: [{ seq: 0, role: "interviewer", phase: null, content: questions[0]!.prompt, created_at: now(), question_index: 0, skipped: false }],
    final_code: null, evaluation: null,
  };
  const requests: { index: number; answer?: string; source?: string; skip?: boolean }[] = [];
  const advance = (index: number, status: "answered" | "skipped", text = "", source?: string) => {
    const qs = iv.questions.map((q) => q.index === index
      ? { ...q, status, answer: status === "answered" ? { ...nurseAnswer, answer: text } : null }
      : q.index === index + 1 ? { ...q, status: "current" as const } : q);
    const done = index + 1 >= qs.length;
    const turns = [...iv.turns, {
      seq: iv.turns.length, role: "candidate" as const, phase: null, content: text, created_at: now(), question_index: index,
      skipped: status === "skipped", source: status === "answered" ? (source as "typed") : null,
      engagement: status === "answered"
        ? { state: "more_detail" as const, label: "Looking for more detail", reason: "Looking for more detail: you described the situation, but not clearly what you personally did. Say “I” for your own actions.", evidence: ["“I” 0×, “we” 3×"] }
        : null,
    }];
    if (!done) turns.push({ seq: turns.length, role: "interviewer", phase: null, content: qs[index + 1]!.prompt, created_at: now(), question_index: index + 1, skipped: false, source: null, engagement: null });
    const answered = qs.filter((q) => q.status === "answered").length;
    iv = {
      ...iv, questions: qs, turns, status: done ? "completed" : "in_progress", ended_at: done ? now() : null,
      round_summary: {
        answered, skipped: qs.filter((q) => q.status === "skipped").length,
        unanswered: qs.filter((q) => q.status === "current" || q.status === "pending").length,
        average_score: answered ? nurseAnswer.score : null, focus: answered ? ["Shares a result, ideally with a number"] : [],
      },
    };
  };
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/interviews/round-1`, () => HttpResponse.json(iv)),
    http.post(`${API}/api/v1/interviews/round-1/answers`, async ({ request }) => {
      const body = (await request.json()) as { question_index: number; answer: string; source: string };
      requests.push({ index: body.question_index, answer: body.answer, source: body.source });
      if (answerDelay) await answerDelay;
      const already = iv.turns.some((t) => t.role === "candidate" && t.question_index === body.question_index);
      if (!already) advance(body.question_index, "answered", body.answer, body.source);
      return HttpResponse.json(iv);
    }),
    http.post(`${API}/api/v1/interviews/round-1/skip`, async ({ request }) => {
      const body = (await request.json()) as { question_index: number };
      requests.push({ index: body.question_index, skip: true });
      advance(body.question_index, "skipped");
      return HttpResponse.json(iv);
    }),
    http.post(`${API}/api/v1/interviews/round-1/abandon`, () => {
      iv = { ...iv, status: "abandoned", ended_at: now(), questions: iv.questions.map((q) => q.status === "current" ? { ...q, status: "pending" } : q) };
      return HttpResponse.json(iv);
    }),
  );
  return { requests, get iv() { return iv; } };
}

afterEach(() => uninstallSpeech());

describe("Voice interview studio", () => {
  it("dictation fills an editable draft: interim text stays separate and nothing submits while listening", async () => {
    installSpeech();
    const srv = roundServer();
    const { user } = renderApp("/interviews/round-1", { signedIn: true });
    expect(await screen.findByRole("heading", { name: nurseQuestions[0]!.title })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Speak answer" }));
    expect(screen.getByText("Listening. Microphone on")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop listening" })).toHaveAttribute("aria-pressed", "true");

    FakeRecognition.latest.emit(["Good assessment means", true], ["checking vital", false]);
    const box = screen.getByLabelText("Your answer");
    expect(box).toHaveValue("Good assessment means");
    expect(screen.getByText("Hearing (not final yet)").parentElement).toHaveTextContent("checking vital");
    // Partial speech can't be submitted: the learner stops and reviews first.
    expect(screen.getByRole("button", { name: "Next question" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Stop listening" }));
    expect(screen.getByText("Processing your speech…")).toBeInTheDocument();
    FakeRecognition.latest.emit(["checking vital signs", true]);
    FakeRecognition.latest.end();
    expect(box).toHaveValue("Good assessment means checking vital signs");
    expect(screen.queryByText("Hearing (not final yet)")).not.toBeInTheDocument();

    // Correct a recognition mistake by typing, then submit: recorded as spoken and edited.
    await user.type(box, " and listening.");
    await user.click(screen.getByRole("button", { name: "Next question" }));
    await waitFor(() => expect(srv.requests).toHaveLength(1));
    expect(srv.requests[0]).toMatchObject({ index: 0, source: "mixed", answer: "Good assessment means checking vital signs and listening." });
    expect(await screen.findByRole("heading", { name: nurseQuestions[1]!.title })).toBeInTheDocument();
    expect(screen.getByLabelText("Your answer")).toHaveValue("");
  });

  it("a blocked microphone keeps the draft, says so, and typing still works", async () => {
    installSpeech();
    const srv = roundServer();
    const { user } = renderApp("/interviews/round-1", { signedIn: true });
    const box = await screen.findByLabelText("Your answer");
    await user.type(box, "I start with the airway.");
    await user.click(screen.getByRole("button", { name: "Speak answer" }));
    FakeRecognition.latest.emit(["breathing then", false]);
    FakeRecognition.latest.fail("not-allowed");
    expect(screen.getByRole("alert")).toHaveTextContent("Microphone access is blocked");
    expect(screen.getByText("Microphone blocked")).toBeInTheDocument();
    expect(box).toHaveValue("I start with the airway."); // the unconfirmed words were not added
    expect(screen.queryByRole("button", { name: "Speak answer" })).not.toBeInTheDocument();
    expect(srv.requests).toHaveLength(0); // nothing was submitted automatically
    await user.click(screen.getByRole("button", { name: "Next question" }));
    await waitFor(() => expect(srv.requests).toEqual([{ index: 0, answer: "I start with the airway.", source: "typed" }]));
  });

  it("an interrupted transcription keeps what was recognised and can be retried", async () => {
    installSpeech();
    roundServer();
    const { user } = renderApp("/interviews/round-1", { signedIn: true });
    const box = await screen.findByLabelText("Your answer");
    await user.click(screen.getByRole("button", { name: "Speak answer" }));
    FakeRecognition.latest.emit(["First I check the patient", true]);
    FakeRecognition.latest.fail("network");
    expect(screen.getByRole("alert")).toHaveTextContent("speech service couldn't be reached");
    expect(box).toHaveValue("First I check the patient");
    await user.click(screen.getByRole("button", { name: "Speak answer" }));
    expect(FakeRecognition.instances).toHaveLength(2);
    expect(screen.getByText("Listening. Microphone on")).toBeInTheDocument();
  });

  it("without speech recognition, voice is explained as unavailable and typing works", async () => {
    const srv = roundServer();
    const { user } = renderApp("/interviews/round-1", { signedIn: true });
    const box = await screen.findByLabelText("Your answer");
    expect(screen.getByText("Voice input unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Speak answer" })).not.toBeInTheDocument();
    expect(screen.getByText(/needs speech recognition, which this browser doesn't offer/)).toBeInTheDocument();
    await user.type(box, "Typed answer.");
    await user.click(screen.getByRole("button", { name: "Next question" }));
    await waitFor(() => expect(srv.requests[0]).toMatchObject({ source: "typed" }));
  });

  it("double clicks and Ctrl+Enter during a request send one answer", async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => { release = r; });
    const srv = roundServer({ answerDelay: gate });
    const { user } = renderApp("/interviews/round-1", { signedIn: true });
    const box = await screen.findByLabelText("Your answer");
    await user.type(box, "One answer only.");
    const submit = screen.getByRole("button", { name: "Next question" });
    await user.dblClick(submit);
    await user.type(box, "{Control>}{Enter}{/Control}");
    await user.click(submit);
    release();
    expect(await screen.findByRole("heading", { name: nurseQuestions[1]!.title })).toBeInTheDocument();
    expect(srv.requests).toHaveLength(1);
  });

  it("the interviewer can be stopped, and its voice is never transcribed as the answer", async () => {
    installSpeech();
    roundServer();
    const { user } = renderApp("/interviews/round-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Read question aloud" }));
    expect(spoken).toEqual([nurseQuestions[0]!.prompt]);
    expect(screen.getByText("Interviewer speaking")).toBeInTheDocument();
    // Start talking while it reads: playback stops first, then the microphone opens.
    await user.click(screen.getByRole("button", { name: "Speak answer" }));
    expect(screen.queryByText("Interviewer speaking")).not.toBeInTheDocument();
    expect(screen.getByText("Listening. Microphone on")).toBeInTheDocument();
    // Replaying the question cancels listening, so playback can't be captured.
    await user.click(screen.getByRole("button", { name: "Read question aloud" }));
    expect(FakeRecognition.latest.aborted).toBe(true);
    expect(screen.getByText("Interviewer speaking")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Stop interviewer" }));
    expect(screen.getByText("Ready")).toBeInTheDocument();
    finishSpeaking();
  });

  it("a reload keeps the unsent draft for the current question", async () => {
    roundServer();
    const first = renderApp("/interviews/round-1", { signedIn: true });
    await first.user.type(await screen.findByLabelText("Your answer"), "Half-written thought");
    first.unmount();
    renderApp("/interviews/round-1", { signedIn: true });
    expect(await screen.findByLabelText("Your answer")).toHaveValue("Half-written thought");
  });

  it("engagement explains itself from the answer, can be hidden, and is reviewable afterwards", async () => {
    const srv = roundServer();
    const { user } = renderApp("/interviews/round-1", { signedIn: true });
    const panel = await screen.findByRole("region", { name: "Simulated interviewer engagement" });
    expect(within(panel).getByText("Not enough evidence yet")).toBeInTheDocument();
    expect(within(panel).getByText(/isn't a real person's opinion/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your answer"), "We handled it as a team and we were fine.");
    await user.click(screen.getByRole("button", { name: "Next question" }));
    expect(await within(panel).findByText("Looking for more detail")).toBeInTheDocument();
    expect(within(panel).getByText(/not clearly what you personally did/)).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Hide" }));
    expect(within(panel).getByText("Hidden. You can review it after the interview.")).toBeInTheDocument();
    expect(within(panel).queryByText("Looking for more detail")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Skip" }));
    await waitFor(() => expect(srv.iv.status).toBe("completed"));
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview results" })).toBeInTheDocument();
    expect(screen.getByText(/1 of 2 answers\. 1 skipped\./)).toBeInTheDocument();
    expect(screen.getByText(/not clearly what you personally did/)).toBeInTheDocument(); // reviewable
    expect(screen.getByText("Skipped")).toBeInTheDocument();
  });

  it("ending early shows the round as ended early, with unreached questions and their saved drafts", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    roundServer();
    const { user } = renderApp("/interviews/round-1", { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Unfinished");
    await user.click(screen.getByRole("button", { name: "End early" }));
    expect(await screen.findByText(/ENDED EARLY/)).toBeInTheDocument();
    expect(screen.getByText("No questions were answered, so there are no scores.", { exact: false })).toBeInTheDocument();
    expect(screen.getAllByText("Not reached")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Finish your saved draft on its own page" })).toHaveAttribute(
      "href", `/careers/registered-nurse/questions/${nurseQuestions[0]!.id}`,
    );
  });
});

describe("Voice setup", () => {
  it("never asks for the microphone until the user chooses to", async () => {
    installSpeech();
    const getUserMedia = vi.fn().mockRejectedValue(Object.assign(new Error("denied"), { name: "NotAllowedError" }));
    Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true });
    server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
    const { user } = renderApp("/interviews", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Voice (optional)" })).toBeInTheDocument();
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(screen.getByText("Available (your browser's speech recognition)")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Enable microphone and test" }));
    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("alert")).toHaveTextContent("Microphone access was blocked");
    expect(screen.getByText("Blocked in this browser")).toBeInTheDocument();
    await user.click(screen.getByText("What's recorded, sent and kept"));
    expect(screen.getByText(/CodeCoach never records or stores audio/)).toBeVisible();
    act(() => undefined);
  });
});
