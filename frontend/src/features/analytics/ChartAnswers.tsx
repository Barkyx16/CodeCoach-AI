import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import type { ChartAttempt } from "@/api/types";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";
import { scoreOnScale } from "@/features/analytics/scale";
import { formatDateTime } from "@/lib/format";

const PAGE = 50;

/**
 * Every answer in the chart's range, each reachable: in the trend or why not, and compared with the
 * answer before it to the same question by the same rules as the question page and an interview
 * retry (docs/COMPARING_ATTEMPTS.md). Read when opened.
 */
export function ChartAnswers({ track, since }: { track: string; since: string | undefined }) {
  const [open, setOpen] = useState(false);
  const q = useInfiniteQuery({
    queryKey: ["me", "career-analytics", track, since ?? "all", "attempts"],
    queryFn: ({ pageParam }) => api.chartAttempts(track, since, pageParam, PAGE),
    initialPageParam: 0,
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined),
    enabled: open,
  });
  const items = q.data?.pages.flatMap((p) => p.items) ?? [];
  const first = q.data?.pages[0];
  return (
    <details className="chart-answers" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>Answers in this range, and which the trend counts</summary>
      {first && (
        <p className="subtle">
          {first.in_chart} of {first.total} {first.total === 1 ? "answer is" : "answers are"} in the trend. Each opens with its own score and feedback.
        </p>
      )}
      <InlineError error={q.error} />
      <ol className="mini-list chart-answers__list">
        {items.map((a) => <ChartAnswerRow key={a.answer_id} a={a} />)}
      </ol>
      {q.hasNextPage && (
        <Button size="sm" variant="secondary" loading={q.isFetchingNextPage} onClick={() => void q.fetchNextPage()}>
          Show more
        </Button>
      )}
    </details>
  );
}

/** The same words as the question page's list: no number for an answer too short to score. */
function scoreLabel(a: ChartAttempt): string {
  if (a.scoring === "too_short") return "Too short to score";
  if (a.scoring === "unknown") return `${scoreOnScale(a.score, a.scale)}, not counted (how it was graded wasn't recorded)`;
  return scoreOnScale(a.score, a.scale);
}

function ChartAnswerRow({ a }: { a: ChartAttempt }) {
  return (
    <li>
      <Link to={a.href}>{a.question_title}</Link>
      {` · ${formatDateTime(a.created_at)} · ${scoreLabel(a)} · `}
      {a.series ? "In the trend" : `Not in the trend: ${a.not_counted}`}
      <br />
      <span className="subtle">
        {a.comparison ? `Compared with your answer before it: ${a.comparison.explanation}` : "Your first answer to this question."}
      </span>
    </li>
  );
}
