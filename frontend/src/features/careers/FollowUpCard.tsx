import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import type { FollowUpOut } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { ActionError } from "@/components/ActionError";
import { conditionsSummary } from "@/features/conditions/summary";
import { dismissalsKey, questionFollowUpKey } from "@/features/dismissals/dismissals";
import { timeAgo } from "@/lib/format";

/**
 * A reviewed follow-up question (docs/FOLLOW_UPS.md): after repeated practice here, an optional,
 * different question about the same thing. Never "new to you" (only what this app saw), never
 * "mastered", and follow-ups you answered stay beside this question's answers with their own
 * scores, never combined. "Not now" is kept with the account, so it holds on every device, and
 * Settings can offer it again (docs/FOLLOW_UPS.md, "Not now").
 */
export function FollowUpCard({ track, questionId, latestAnswerId, answeredCount }: {
  track: string; questionId: string; latestAnswerId: string | null; answeredCount: number;
}) {
  const queryClient = useQueryClient();
  const q = useQuery<FollowUpOut>({
    queryKey: ["me", "follow-up", track, questionId, answeredCount],
    queryFn: () => api.followUp(track, questionId),
    enabled: answeredCount > 0,
  });
  const notNow = useMutation({
    mutationFn: (to: string) => api.dismiss([{ key: questionFollowUpKey(track, questionId, to), offered_on: window.location.pathname }]),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["me", "follow-up", track, questionId] });
      void queryClient.invalidateQueries({ queryKey: dismissalsKey });
    },
  });
  if (!q.data) return null;
  const data = q.data;
  const offers = data.offers.filter((o) => !(notNow.isSuccess && notNow.variables === o.question_id));
  const showNone = data.status === "none" && data.scored_answers >= data.threshold;
  if (!offers.length && !showNone && !data.answered.length) return null;
  return (
    <section className="card stack-sm follow-up" aria-labelledby="follow-up-title">
      <h2 className="section-title" id="follow-up-title">A related question</h2>
      {showNone && <p className="subtle">{data.message}</p>}
      {data.status === "offered" && offers.map((o) => (
        <div key={o.question_id} className="stack-sm">
          <p className="subtle">{data.message}</p>
          <p>
            <Link to={`/careers/${o.track}/questions/${o.question_id}${latestAnswerId ? `?followUpOf=${encodeURIComponent(latestAnswerId)}` : ""}`}>
              {o.title}
            </Link>
            {o.version > 1 && <>{" "}<Badge>Version {o.version}</Badge></>}
          </p>
          <p><strong>The same:</strong> {o.objective}</p>
          <p><strong>Different:</strong> {o.difference}</p>
          <p className="subtle">{o.exposure}.</p>
          <span className="row">
            <Button size="sm" variant="ghost" loading={notNow.isPending && notNow.variables === o.question_id}
              onClick={() => notNow.mutate(o.question_id)}>Not now</Button>
          </span>
        </div>
      ))}
      {notNow.error && <ActionError error={notNow.error} action="Saving “Not now”" />}
      {data.answered.length > 0 && (
        <>
          <h3 className="section-title">Follow-ups you answered</h3>
          <p className="subtle">Each is its own answer with its own score, kept beside yours here. Scores aren't combined, and a result either way is more evidence, not a verdict.</p>
          <ul className="mini-list">
            {data.answered.map((a) => (
              <li key={a.answer_id}>
                <Link to={`/careers/${a.track}/questions/${a.question_id}?answer=${encodeURIComponent(a.answer_id)}`}>{a.title}</Link>
                {": "}
                {a.evidence_level === "insufficient" ? "Too short to score" : `${a.score}/100 · ${a.rating}`}
                {` · ${timeAgo(a.created_at)}`}
                {a.content_version > 1 ? ` · version ${a.content_version}` : ""}
                {a.conditions ? ` · In-app help: ${conditionsSummary(a.conditions)}` : ""}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

