import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { useCapabilities } from "@/api/queries";
import { Button } from "@/components/Button";

import { JUDGE_REFUSALS } from "./judgeRefusals";

/**
 * The way on after the judge refused a run or submission (Volume 8, prompt 7; RECOVERY.md). A
 * refusal isn't a job: nothing was queued. Shown inside the action's error, next to the editor,
 * which stays as it was:
 * - still being judged (`submission_pending`): back to that submission, not a fresh submit;
 * - queue full (`judge_busy`): the server's wait when it has one (a hint for when to try again,
 *   not when anything will be judged); otherwise Check availability;
 * - judge unavailable (`judge_unavailable`): Check availability, and for a run, Submit instead
 *   (a submission waits in the queue);
 * - not configured (`execution_disabled`): code can't run here. Save the attempt or ask the
 *   coach; no Try again, since it can't help.
 * Copy code is there for each. Nothing here sends anything by itself.
 */

export function JudgeRecovery({ error, mode, problemSlug, code, onShowSubmission, onSubmitInstead, onAskCoach }: {
  error: unknown;
  mode: "run" | "submit";
  problemSlug: string;
  code: string;
  onShowSubmission(id: string): void;
  onSubmitInstead(): void;
  onAskCoach(): void;
}) {
  const capabilities = useCapabilities();
  const [checked, setChecked] = useState<{ at: number; ready: boolean; message: string } | null>(null);
  const [copied, setCopied] = useState<"yes" | "no" | null>(null);
  if (!(error instanceof ApiError) || !JUDGE_REFUSALS.includes(error.code)) return null;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied("yes");
    } catch {
      setCopied("no");
    }
  };
  const copyButton = (
    <>
      <Button size="sm" variant="ghost" onClick={() => void copy()}>Copy code</Button>
      {copied && <span className="subtle" role="status">{copied === "yes" ? "Copied." : "This browser didn't allow copying."}</span>}
    </>
  );
  // One read of the capabilities (the server checks the judge at most every 15 s); never repeated by itself.
  const check = async () => {
    const result = await capabilities.refetch();
    const execution = result.data?.execution;
    setChecked({
      at: Date.now(),
      ready: execution?.state === "ready",
      message: result.isError ? "We couldn't check just now." : execution?.message ?? "",
    });
  };
  const checkButton = (
    <>
      <Button size="sm" variant="secondary" loading={capabilities.isFetching} onClick={() => void check()}>Check availability</Button>
      {checked && (
        <span className="subtle" role="status">
          Checked at {new Date(checked.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}:{" "}
          {checked.ready ? "the judge is ready. You can try again." : checked.message}
        </span>
      )}
    </>
  );

  if (error.code === "submission_pending") {
    const d = (error.details ?? {}) as { pending_submission_id?: string | null; problem_slug?: string | null; mode?: string | null };
    const what = d.mode === "run" ? "run" : "submission";
    if (!d.pending_submission_id) return <span className="subtle">Its result appears when it's done; then you can send another.</span>;
    return (
      <>
        <span className="subtle">Nothing new was sent. Your earlier {what} is still in the queue or being judged; its result appears when it's done.</span>
        {d.problem_slug === problemSlug || !d.problem_slug
          ? <Button size="sm" variant="secondary" onClick={() => onShowSubmission(d.pending_submission_id!)}>Show its status</Button>
          : <Link className="btn btn--secondary btn--sm" to={`/problems/${d.problem_slug}`}>Open that problem</Link>}
      </>
    );
  }
  if (error.code === "execution_disabled") {
    return (
      <>
        {mode === "run" && <Button size="sm" variant="secondary" onClick={onSubmitInstead}>Save attempt instead</Button>}
        <Button size="sm" variant="ghost" onClick={onAskCoach}>Ask the coach for a review</Button>
        {copyButton}
      </>
    );
  }
  const hasWait = error.retryAt !== null;
  return (
    <>
      {error.code === "judge_busy" && hasWait && (
        <span className="subtle">That's the server's suggestion for when to try again, not when your code would be judged.</span>
      )}
      {!hasWait && checkButton}
      {error.code === "judge_unavailable" && mode === "run" && (
        <Button size="sm" variant="ghost" onClick={onSubmitInstead}>Submit instead (it waits in the queue)</Button>
      )}
      {copyButton}
    </>
  );
}
