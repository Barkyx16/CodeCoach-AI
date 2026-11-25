import { Link } from "react-router-dom";

import { useSampleLessons } from "@/api/queries";
import { Card } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/States";

/** /compare: authored sample-answer lessons (Volume 10, prompt 6). Read two answers to one question,
 * mark what helps or hurts each and say why, then compare with an authored explanation. */
export function SampleLessonList() {
  const lessons = useSampleLessons();
  return (
    <div className="page cmp-list">
      <div className="page__header">
        <div>
          <p className="eyebrow">COMPARE SAMPLE ANSWERS</p>
          <h1 className="page__title">Learn what makes an answer useful</h1>
          <p className="page__subtitle">
            Each lesson shows one interview question and two made-up answers. Mark the sentences that help or hurt, say why in a few
            words, then read an explanation tied to what interviewers look for. Your reasons matter more than which answer you pick.
          </p>
        </div>
      </div>
      {lessons.isPending ? <LoadingState label="Loading lessons…" />
        : lessons.isError ? <ErrorState error={lessons.error} onRetry={() => void lessons.refetch()} />
          : (
            <ul className="stack">
              {lessons.data.map((l) => (
                <li key={l.id}>
                  <Card className="stack-sm">
                    <h2 className="section-title"><Link to={`/compare/${l.id}`}>{l.title}</Link></h2>
                    <p className="subtle">{l.teaching_goal}</p>
                  </Card>
                </li>
              ))}
            </ul>
          )}
    </div>
  );
}
