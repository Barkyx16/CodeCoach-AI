import { Link } from "react-router-dom";

import { useRelatedPractice } from "@/api/queries";
import type { RelatedAttempt, RelatedPractice as Practice } from "@/api/types";
import { formatDay } from "@/features/applications/dates";

function scoreText(a: RelatedAttempt): string {
  if (a.scoring === "too_short") return "too short to score";
  if (a.scoring === "unknown" || a.score === null || a.score === undefined) return "score not recorded";
  return `${a.score}/100`;
}

/** How a retry's score stands next to the attempt it came from: only when the rule says the scores compare. */
function against(a: RelatedAttempt, p: Practice): string | null {
  const from = p.origin;
  if (a.kind !== "retry" || !a.comparison?.scores_comparable || !from || from.score === null || from.score === undefined) return null;
  if (a.score === null || a.score === undefined) return null;
  const word = a.score > from.score ? "higher than" : a.score < from.score ? "lower than" : "the same as";
  return `${word} the ${from.score}/100 it came from`;
}

/**
 * Practice related to an accepted improvement since it was accepted (docs/ACCEPTED_ACTIONS.md):
 * retries of its question and follow-ups to it, found by stored links, each with its own score and
 * how it compares. Evidence only: it never ticks the action or says the improvement worked. The plan
 * and the kit both show this, from the same request.
 */
export function RelatedPractice({ actionId }: { actionId: string }) {
  const q = useRelatedPractice(actionId);
  if (q.isPending) return null;
  if (q.isError) return <p className="subtle">Related practice couldn't be loaded.</p>;
  const p = q.data;
  if (!p.linked) return <p className="subtle related-practice">{p.note}</p>;
  return (
    <details className="related-practice">
      <summary>Related practice since you accepted it ({p.count})</summary>
      {p.disputed && <p className="subtle">It came from feedback you disputed; its practice is still shown.</p>}
      {p.count === 0 ? <p className="subtle">Nothing yet.</p> : (
        <ol className="mini-list">
          {p.items.map((a) => {
            const cmp = against(a, p);
            return (
              <li key={a.answer_id}>
                <Link to={a.href}>{a.kind === "retry" ? "Retry" : "Follow-up"}: {a.question_title}</Link>
                {", "}<time dateTime={a.created_at}>{formatDay(a.created_at.slice(0, 10))}</time>
                {" · "}{scoreText(a)}{cmp ? `, ${cmp}` : ""}
                {a.kind === "follow_up" && a.note ? <span className="subtle"> {a.note}</span>
                  : a.comparison ? <span className="subtle"> {a.comparison.explanation}</span> : null}
              </li>
            );
          })}
        </ol>
      )}
      <p className="subtle">{p.note}</p>
    </details>
  );
}
