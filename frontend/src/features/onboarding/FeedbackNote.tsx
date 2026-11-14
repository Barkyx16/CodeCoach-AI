import type { Capabilities } from "@/api/types";

/** Says what feedback the first activity will really get, before anyone promises it. */
export function FeedbackNote({ kind, execution }: { kind: "question" | "problem"; execution?: Capabilities["execution"] }) {
  if (kind === "question") {
    return (
      <p className="subtle">
        You'll get feedback from CodeCoach's built-in rubric coach: what your answer covered and what to add.
        It isn't an AI model, and it isn't a hiring decision.
      </p>
    );
  }
  if (!execution) return <p className="subtle">Your code is checked by the server's judge when one is available.</p>;
  if (execution.state === "ready") {
    return <p className="subtle">Your code is checked against hidden tests on the server. The coach can give hints and reviews; it never changes the verdict.</p>;
  }
  return execution.submit_mode === "saved_only"
    ? <p className="subtle">Code can't be judged on this server right now: you can write and save your attempt and ask the coach for a review, but there won't be a pass or fail.</p>
    : <p className="subtle">The code judge is temporarily unavailable: submissions wait in a queue and are checked when it's back.</p>;
}
