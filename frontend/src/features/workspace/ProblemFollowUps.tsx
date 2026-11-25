import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import type { FollowUpOf, ProblemFollowUpsOut } from "@/api/types";
import { ActionError } from "@/components/ActionError";
import { StatusBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { timeAgo } from "@/lib/format";

const problemFollowUpsKey = (slug: string) => ["me", "problem-follow-ups", slug] as const;

/**
 * A reviewed follow-up coding problem (docs/FOLLOW_UPS.md, "Coding problems"): after a judged
 * submission of this problem passed, an optional, different problem that shares one idea with it,
 * offered only while it hasn't been attempted here. Dismissing it is kept with the account. The
 * follow-ups submitted from here are listed with their own verdicts, never combined with this
 * problem's or compared with them.
 *
 * `part`: "offer" in the results (after a passed submission: at phone size, in the Code tab),
 * "answered" beside the problem, or "both" when there's no result on screen to put the offer under.
 */
export function ProblemFollowUps({ slug, part, refreshKey }: { slug: string; part: "offer" | "answered" | "both"; refreshKey?: string | null }) {
  const queryClient = useQueryClient();
  const q = useQuery<ProblemFollowUpsOut>({
    queryKey: [...problemFollowUpsKey(slug), refreshKey ?? ""],
    queryFn: () => api.problemFollowUps(slug),
  });
  const dismiss = useMutation({
    mutationFn: (to: string) => api.dismissProblemFollowUp(slug, to),
    onSuccess: (data) => {
      queryClient.setQueryData([...problemFollowUpsKey(slug), refreshKey ?? ""], data);
      void queryClient.invalidateQueries({ queryKey: problemFollowUpsKey(slug) });
    },
  });
  if (!q.data) return null;
  const data = q.data;
  const offers = part !== "answered" && data.status === "offered" ? data.offers : [];
  const answered = part !== "offer" ? data.answered : [];
  if (!offers.length && !answered.length) return null;
  return (
    <section className="card stack-sm follow-up" aria-label={offers.length ? "A related problem" : "Follow-ups you submitted"}>
      {offers.length > 0 && (
        <>
          <h3 className="section-title">A related problem</h3>
          <p className="subtle">{data.message}</p>
          {offers.map((o) => (
            <div key={o.slug} className="stack-sm">
              <p><Link to={`/problems/${encodeURIComponent(o.slug)}?followUpOf=${encodeURIComponent(o.from_submission_id)}`}>{o.title}</Link>
                {" "}<span className="subtle">({o.difficulty.toLowerCase()})</span></p>
              <p><strong>The same:</strong> {o.shares}</p>
              <p><strong>Different:</strong> {o.difference}</p>
              <p className="subtle">{o.exposure}.</p>
              <span className="row">
                <Button size="sm" variant="ghost" loading={dismiss.isPending && dismiss.variables === o.slug}
                  aria-label={`Not now: ${o.title}`} onClick={() => dismiss.mutate(o.slug)}>Not now</Button>
              </span>
            </div>
          ))}
          {dismiss.error && <ActionError error={dismiss.error} action="Hiding the related problem" />}
        </>
      )}
      {answered.length > 0 && (
        <>
          <h3 className="section-title">Follow-ups you submitted</h3>
          <p className="subtle">Each is a different problem with its own verdict, not combined with this problem's or compared with it.</p>
          <ul className="mini-list">
            {answered.map((a) => (
              <li key={a.submission_id}>
                <Link to={`/history/submissions/${encodeURIComponent(a.submission_id)}`}>{a.title}</Link>{": "}
                <StatusBadge status={a.status} />
                {a.passed_count != null && a.total_count != null && <span className="subtle"> {a.passed_count} of {a.total_count} tests passed</span>}
                <span className="subtle"> · {timeAgo(a.created_at)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

/** On a follow-up's own result and page: which different problem it followed, and that it isn't compared. */
export function FollowsUpNote({ of }: { of: FollowUpOf }) {
  return (
    <p className="subtle follow-up__of" data-testid="follows-up">
      {of.text}{" "}
      <Link to={`/history/submissions/${encodeURIComponent(of.submission_id)}`}>See that submission</Link>
    </p>
  );
}
