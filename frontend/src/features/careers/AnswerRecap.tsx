import { Link } from "react-router-dom";

import { useQuestions } from "@/api/queries";
import type { Difficulty, InterviewAnswer, QuestionSummary } from "@/api/types";
import { Button } from "@/components/Button";
import { timeAgo } from "@/lib/format";

import { compareTries, revisionTarget } from "./tries";

/** The library lists at most this many questions per request; no level holds more. */
const LEVEL_PAGE = 100;

/** The next unanswered question at this level, after this one in library order (wrapping round). */
function nextUnanswered(items: QuestionSummary[], currentId: string): QuestionSummary | null {
  const at = items.findIndex((x) => x.id === currentId);
  const ordered = at < 0 ? items : [...items.slice(at + 1), ...items.slice(0, at)];
  return ordered.find((x) => x.id !== currentId && x.best_score == null) ?? null;
}

function list(labels: string[]): string {
  const quoted = labels.map((l) => `“${l}”`);
  return quoted.length <= 1 ? quoted.join("") : `${quoted.slice(0, -1).join(", ")} and ${quoted.at(-1)}`;
}

/**
 * What happened in this try and one way on, from the answer record alone: the points it covered
 * (structure, not whether the details are right), how it compares with the try before when the two
 * were graded the same way, and a revision aimed at one missing point or the next question.
 */
export function AnswerRecap({ answer, tryNo, previous, previousNo, track, questionId, difficulty, backTo, canRevise, onRevise }: {
  answer: InterviewAnswer;
  tryNo: number | null;
  previous: InterviewAnswer | null;
  previousNo: number | null;
  track: string;
  questionId: string;
  difficulty: Difficulty;
  /** The list this question was opened from (the breadcrumb at the top already leads there). */
  backTo: string;
  /** Signed in, online and the question still graded. */
  canRevise: boolean;
  onRevise: (target: { label: string; advice: string } | null) => void;
}) {
  const level = useQuestions(track, { difficulty, page: 1, page_size: LEVEL_PAGE });
  const next = level.data ? nextUnanswered(level.data.items, questionId) : null;
  const insufficient = answer.evidence_level === "insufficient";
  const target = revisionTarget(answer);
  const covered = answer.points.filter((p) => p.covered).length;
  const total = answer.points.length;
  const reviseFirst = canRevise && (insufficient || target !== null);
  const which = tryNo ? `try ${tryNo}` : "this try";

  const outcome = insufficient
    ? `${which[0]!.toUpperCase()}${which.slice(1)} was too short to score yet (${answer.word_count} ${answer.word_count === 1 ? "word" : "words"}).`
    : target
      ? `${which[0]!.toUpperCase()}${which.slice(1)} covered ${covered} of ${total} points the rubric looks for. To add: “${target.label}”.`
      : `${which[0]!.toUpperCase()}${which.slice(1)} covered all ${total} points the rubric looks for.`;

  let comparison: string | null = null;
  if (previous) {
    const before = previousNo ? `try ${previousNo}` : `your answer from ${timeAgo(previous.created_at)}`;
    const c = compareTries(previous, answer);
    if (!c.comparable) {
      comparison = `Not directly comparable with ${before}: ${c.reasons.join("; ")}.`;
    } else {
      const parts = [
        c.gained.length ? `now covers ${list(c.gained)}` : null,
        c.lost.length ? `no longer covers ${list(c.lost)}` : null,
      ].filter(Boolean);
      const score = c.scoreFrom === c.scoreTo ? `score ${c.scoreTo} both times` : `score ${c.scoreFrom}, now ${c.scoreTo}`;
      comparison = `Compared with ${before} (same question version, rubric and coach): ${parts.length ? parts.join("; ") : "covers the same points"}; ${score}.`;
    }
  }

  const revise = (
    <Button variant={reviseFirst ? "primary" : "secondary"} onClick={() => onRevise(insufficient ? null : target)}>
      {insufficient ? "Add to this answer" : target ? "Revise this answer" : "Revise anyway"}
    </Button>
  );
  const nextLink = next
    ? <Link to={`/careers/${track}/questions/${next.id}`} state={{ listFrom: backTo }} className={`btn btn--${reviseFirst ? "secondary" : "primary"} btn--md`}>Next question: {next.title}</Link>
    : null;

  return (
    <section className="card stack answer-recap" aria-labelledby="recap-title">
      <h2 className="section-title" id="recap-title">What next</h2>
      <p>{outcome}</p>
      {comparison && <p className="subtle">{comparison}</p>}
      <div className="row answer-recap__actions">
        {canRevise && reviseFirst && revise}
        {nextLink}
        {canRevise && !reviseFirst && revise}
      </div>
      {!next && level.data && level.data.items.length >= level.data.total && (
        <p className="subtle">Every other {difficulty} question here has an answer; the <Link to={backTo}>question library</Link> has the other levels.</p>
      )}
    </section>
  );
}
