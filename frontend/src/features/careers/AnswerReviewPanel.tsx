import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api } from "@/api/endpoints";
import { useAnswerReview } from "@/api/queries";
import type { AnswerReview, SelfRating } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";
import { formatDateTime } from "@/lib/format";

const RATING_LABEL: Record<SelfRating, string> = { no: "Not yet", partly: "Partly", yes: "Yes" };
const OVERALL = "Overall";

/**
 * Your reflection beside the coach's feedback, without declaring a winner; private flags on a
 * criterion; and a re-check only when the rubric or question changed. The original result is
 * never replaced.
 */
export function AnswerReviewPanel({ answerId, defaultOpen = false }: { answerId: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details className="card answer-review-disclosure" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>Your reflection, flags and checking again</summary>
      {open && <ReviewBody answerId={answerId} />}
    </details>
  );
}

function ReviewBody({ answerId }: { answerId: string }) {
  const review = useAnswerReview(answerId);
  const qc = useQueryClient();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [flagging, setFlagging] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  if (!review.data) return review.isError ? <InlineError error={review.error} /> : <p className="subtle">Loading…</p>;
  const r = review.data;
  const put = (next: AnswerReview) => qc.setQueryData(["me", "answer-review", answerId], next);

  async function run(fn: () => Promise<AnswerReview>) {
    setBusy(true);
    setError(null);
    try {
      put(await fn());
      // A dispute changes what's recommended (docs/DISPUTES.md): the plan, accepted improvements and
      // the schedule read it again.
      for (const key of [["me", "plan"], ["me", "actions"], ["me", "schedule"]]) void qc.invalidateQueries({ queryKey: key });
      return true;
    } catch (e) {
      setError(e);
      return false;
    } finally {
      setBusy(false);
    }
  }

  const hasRatings = r.perspectives.some((p) => p.yours !== null);
  const flagFor = (criterion: string) => r.flags.find((f) => f.criterion === criterion);

  return (
    <section className="stack answer-review" aria-labelledby="answer-review-title">
      <h2 className="visually-hidden" id="answer-review-title">Your reflection and the coach's feedback</h2>
      <p className="subtle">
        Three different things: <strong>your reflection</strong> (your view), <strong>the coach's points</strong> (built-in rules looking for
        each point in your words) and <strong>fixed checks</strong> like length. Neither view proves the other right.
      </p>

      {r.self_review && !r.self_review.skipped ? (
        <div className="stack-sm">
          <h3 className="section-title">Different perspectives</h3>
          {(r.self_review.went_well || r.self_review.improve) && (
            <dl className="answer-review__notes">
              {r.self_review.went_well && <><dt>You said went well</dt><dd>{r.self_review.went_well}</dd></>}
              {r.self_review.improve && <><dt>You'd improve</dt><dd>{r.self_review.improve}</dd></>}
            </dl>
          )}
          {hasRatings && (
            <table className="answer-review__table">
              <caption className="visually-hidden">Your ratings beside what the coach found</caption>
              <thead><tr><th scope="col">Point</th><th scope="col">You</th><th scope="col">Coach</th></tr></thead>
              <tbody>
                {r.perspectives.map((p) => (
                  <tr key={p.criterion}>
                    <th scope="row">{p.criterion}</th>
                    <td>{p.yours ? RATING_LABEL[p.yours] : "Not rated"}</td>
                    <td>{p.coach ? "Found" : "Not found"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="subtle">{r.self_review.before_feedback ? "Written before you read the feedback." : "Written or edited after reading the feedback."}</p>
        </div>
      ) : (
        <p className="subtle">{r.self_review?.skipped ? "You skipped the reflection for this answer. That's fine." : "No reflection for this answer."}</p>
      )}

      {r.repeated.length > 0 && (
        <div className="stack-sm">
          <h3 className="section-title">Came up more than once</h3>
          <p className="subtle">Points the coach didn't find here and in other recent answers on this career: somewhere to look, not a verdict.</p>
          <ul className="mini-list">{r.repeated.map((x) => <li key={x.criterion}>{x.criterion}: not found in {x.times} of your last {x.of} answers</li>)}</ul>
        </div>
      )}

      <div className="stack-sm">
        <h3 className="section-title">Something unclear, or you disagree?</h3>
        <p className="subtle">
          Flags are private notes for you. "I disagree" keeps that point out of your automatic plan until you count it again; your score and the feedback don't change. A real problem with the question itself goes through "Report a problem" on the feedback.
        </p>
        <ul className="answer-review__flags">
          {[...r.answer.points.map((p) => p.label), OVERALL].map((criterion) => {
            const f = flagFor(criterion);
            return (
              <li key={criterion}>
                <span>{criterion === OVERALL ? "The feedback overall" : criterion}</span>
                {f ? (
                  <span className="stack-sm">
                    <span className="row">
                      <Badge tone="warning">{f.kind === "unclear" ? "Unclear to you" : f.disputed ? "You disagree" : "You disagreed"}</Badge>
                      {f.note && <span className="subtle">“{f.note}”</span>}
                      <Button size="sm" variant="ghost" disabled={busy} onClick={() => void run(() => api.removeAnswerFlag(answerId, f.id))}>Remove flag</Button>
                    </span>
                    {f.disputed && (
                      <span className="row">
                        <span className="subtle">
                          Disputed{f.disputed_at ? ` on ${formatDay(f.disputed_at)}` : ""}: this point doesn't shape your plan until you count it again.
                        </span>
                        <Button size="sm" variant="secondary" disabled={busy} onClick={() => void run(() => api.reinstateAnswerFlag(answerId, f.id))}>
                          Count it in my plan again
                        </Button>
                      </span>
                    )}
                    {f.kind === "disagree" && !f.disputed && f.reinstated_at && (
                      <span className="subtle">Counted in your plan again since {formatDay(f.reinstated_at)}.</span>
                    )}
                  </span>
                ) : flagging === criterion ? (
                  <FlagForm busy={busy} onCancel={() => setFlagging(null)}
                    onSave={async (kind, note) => { if (await run(() => api.addAnswerFlag(answerId, { criterion, kind, note }))) setFlagging(null); }} />
                ) : (
                  <Button size="sm" variant="ghost" aria-label={`Flag “${criterion === OVERALL ? "the feedback overall" : criterion}”`} onClick={() => setFlagging(criterion)}>Flag</Button>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <div className="stack-sm">
        <h3 className="section-title">Check again</h3>
        <p className="subtle">{r.reevaluate_note}</p>
        {r.can_reevaluate && (
          <form className="stack-sm" onSubmit={(e: FormEvent) => { e.preventDefault(); void run(() => api.reevaluateAnswer(answerId, reason)).then((ok) => ok && setReason("")); }}>
            <label className="field"><span className="field__label">Why (optional, private)</span>
              <input className="input" maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
            </label>
            <span><Button type="submit" size="sm" loading={busy}>Check again with the current rubric</Button></span>
          </form>
        )}
        {r.evaluations.length > 0 && (
          <ul className="mini-list">
            <li>Original: score {r.answer.score} ({r.answer.rating}), rubric {r.answer.rubric_version}, question version {r.answer.content_version}. Kept as it was.</li>
            {r.evaluations.map((e) => (
              <li key={e.id}>
                Checked again {formatDateTime(e.created_at)}: {e.evidence_level === "insufficient" ? "not enough to score" : `score ${e.score} (${e.rating})`}, rubric {e.rubric_version}, question version {e.content_version}. {e.summary}
              </li>
            ))}
          </ul>
        )}
      </div>
      <InlineError error={error} />
    </section>
  );
}

function FlagForm({ busy, onSave, onCancel }: { busy: boolean; onSave: (kind: "unclear" | "disagree", note: string) => void; onCancel: () => void }) {
  const [kind, setKind] = useState<"unclear" | "disagree">("unclear");
  const [note, setNote] = useState("");
  return (
    <form className="stack-sm answer-review__flag-form" onSubmit={(e) => { e.preventDefault(); onSave(kind, note); }}>
      <fieldset className="row">
        <legend className="visually-hidden">What kind of flag</legend>
        <label className="checkbox"><input type="radio" name="flag-kind" checked={kind === "unclear"} onChange={() => setKind("unclear")} />It's unclear</label>
        <label className="checkbox"><input type="radio" name="flag-kind" checked={kind === "disagree"} onChange={() => setKind("disagree")} />I disagree</label>
      </fieldset>
      <label className="field"><span className="field__label">Private note (optional)</span>
        <input className="input" maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
      </label>
      <span className="row">
        <Button type="submit" size="sm" variant="primary" loading={busy}>Save flag</Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
      </span>
    </form>
  );
}

// The same day, worded the same way, as the plan's server-written lines ("on 3 November", the UTC
// calendar day), so the flag and the plan never name different days (docs/DISPUTES.md).
const DAY = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", timeZone: "UTC" });
const formatDay = (iso: string) => DAY.format(new Date(iso));
