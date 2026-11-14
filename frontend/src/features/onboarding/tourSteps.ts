import type { Capabilities, TourKind } from "@/api/types";

/** What a step can know about the page it's explaining, so it never promises what isn't there. */
export interface TourContext {
  execution?: Capabilities["execution"];
  signedIn: boolean;
}

export interface TourStep {
  /** Matches a `data-tour` attribute on the real element this step explains. */
  target: string;
  title: string;
  body: string | ((ctx: TourContext) => string);
  /** Shown when the element isn't on screen (not there yet, another tab, or hidden in focus mode). */
  missing: string;
}

/** Five steps each: the server's TOUR_STEPS (app/services/onboarding.py) must match. */
export const TOUR_STEPS: Record<TourKind, TourStep[]> = {
  written: [
    {
      target: "question",
      title: "Read the question",
      body: "Read it first. Questions come from your career's question bank, and “About this question” says how each one was made.",
      missing: "The question is near the top of this page.",
    },
    {
      target: "answer",
      title: "Your answer",
      body: "Write it the way you'd say it in the interview. Around 120 to 350 words is a good length; there's no timer here.",
      missing: "The answer box is below the question.",
    },
    {
      target: "draft",
      title: "Your draft is kept",
      body: "While you type, your draft is saved in this browser. Nothing is sent anywhere until you choose Get feedback.",
      missing: "This appears below the answer box.",
    },
    {
      target: "feedback",
      title: "Getting feedback",
      body: (ctx) => ctx.signedIn
        ? "Get feedback checks your answer against what a strong answer covers and shows what to add. It comes from CodeCoach's built-in rubric coach, not an AI model, and it isn't a hiring decision."
        : "Feedback needs an account so your answers are saved: sign in, or try it as a guest in one click.",
      missing: "The Get feedback button is below the answer box.",
    },
    {
      target: "next",
      title: "What to do next",
      body: "Your feedback lists what the answer covered and what to add. Under it, What next offers a revision aimed at one missing point, or the next question; you can also save this one for later. Every answer stays in History.",
      missing: "This part appears after you get feedback on an answer. You can finish the introduction now; nothing here depends on it.",
    },
  ],
  coding: [
    {
      target: "statement",
      title: "The problem",
      body: "Read the problem, its examples and constraints. Hidden tests check more cases than the examples show.",
      missing: "Open the Problem tab to read it.",
    },
    {
      target: "editor",
      title: "The editor",
      body: "Write Java here. Tab indents; to move focus out of the editor with Tab, press Ctrl+M first (on a Mac, Ctrl+Shift+M).",
      missing: "Open the Code tab to see the editor.",
    },
    {
      target: "save",
      title: "Your draft is kept",
      body: "Your code is saved in this browser as you type. Nothing is submitted until you choose to; Reset goes back to the starter code.",
      missing: "Open the Code tab: the save status is above the editor.",
    },
    {
      target: "submit",
      title: "Checking your code",
      body: (ctx) => {
        if (!ctx.execution) return "Submit sends your code to the server's judge, when one is available.";
        if (ctx.execution.state === "ready") {
          return ctx.execution.run_available
            ? "Run checks the public examples; Submit runs the hidden tests on the server and gives the verdict. Ctrl+Enter submits."
            : "Submit runs the hidden tests on the server and gives the verdict. Ctrl+Enter submits.";
        }
        return ctx.execution.submit_mode === "saved_only"
          ? "Code can't be judged on this server right now, so the button saves your attempt without a verdict. The coach can still review your code."
          : "The judge is temporarily unavailable. Submitting queues your code, and the verdict appears when it's checked.";
      },
      missing: "Open the Code tab: the buttons are above the editor.",
    },
    {
      target: "coach",
      title: "The coach",
      body: "Stuck? Ask for a hint, one level at a time, or a review of your code. The coach explains; it never changes the verdict.",
      missing: "Open the Coach tab to ask for a hint or a review.",
    },
  ],
};
