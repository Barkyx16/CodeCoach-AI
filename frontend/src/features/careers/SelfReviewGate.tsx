import { useState, type FormEvent } from "react";

import { api } from "@/api/endpoints";
import type { InterviewAnswer, SelfRating } from "@/api/types";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";

const RATINGS: { value: SelfRating; label: string }[] = [
  { value: "no", label: "Not yet" },
  { value: "partly", label: "Partly" },
  { value: "yes", label: "Yes" },
];

/**
 * Your own read of the answer before the coach's. The answer is already saved; nothing here
 * changes it or its result, and skipping costs nothing.
 */
export function SelfReviewGate({ answer, onDone }: { answer: InterviewAnswer; onDone: () => void }) {
  const [wentWell, setWentWell] = useState("");
  const [improve, setImprove] = useState("");
  const [ratings, setRatings] = useState<Record<string, SelfRating>>({});
  const [busy, setBusy] = useState<"save" | "skip" | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function send(skipped: boolean, e?: FormEvent) {
    e?.preventDefault();
    setBusy(skipped ? "skip" : "save");
    setError(null);
    try {
      await api.saveSelfReview(answer.id, { went_well: wentWell, improve, ratings, skipped, before_feedback: true });
      onDone();
    } catch (err) {
      setError(err); // the reflection stays here; "Show feedback without saving" still works
    } finally {
      setBusy(null);
    }
  }

  return (
    <form className="card stack self-review" aria-labelledby="self-review-title" onSubmit={(e) => void send(false, e)}>
      <h2 className="section-title" id="self-review-title">Before you read the feedback</h2>
      <p className="subtle">Your answer is saved. This is optional: your own reflection, kept apart from the answer and never changing its result.</p>
      <label className="field"><span className="field__label">What went well?</span>
        <textarea className="input" rows={2} maxLength={2000} value={wentWell} onChange={(e) => setWentWell(e.target.value)} />
      </label>
      <label className="field"><span className="field__label">What would you improve?</span>
        <textarea className="input" rows={2} maxLength={2000} value={improve} onChange={(e) => setImprove(e.target.value)} />
      </label>
      <fieldset className="stack-sm self-review__ratings">
        <legend className="field__label">Did your answer do these? (optional)</legend>
        {answer.points.map((p, i) => (
          <div key={p.label} className="self-review__row" role="radiogroup" aria-labelledby={`sr-${i}`}>
            <span id={`sr-${i}`}>{p.label}</span>
            <span className="row">
              {RATINGS.map((r) => (
                <label key={r.value} className="checkbox">
                  <input type="radio" name={`sr-${i}`} value={r.value} checked={ratings[p.label] === r.value}
                    onChange={() => setRatings((x) => ({ ...x, [p.label]: r.value }))} />
                  {r.label}
                </label>
              ))}
            </span>
          </div>
        ))}
      </fieldset>
      <InlineError error={error} />
      <span className="row">
        <Button type="submit" variant="primary" loading={busy === "save"}>Save and show feedback</Button>
        <Button variant="ghost" loading={busy === "skip"} onClick={() => void send(true)}>Skip and show feedback</Button>
        {error !== null && <Button variant="ghost" onClick={onDone}>Show feedback without saving</Button>}
      </span>
    </form>
  );
}
