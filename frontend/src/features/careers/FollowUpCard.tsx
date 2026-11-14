import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import type { FollowUpOut } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { conditionsSummary } from "@/features/conditions/summary";
import { timeAgo } from "@/lib/format";

/**
 * A reviewed follow-up question (docs/FOLLOW_UPS.md): after repeated practice here, an optional,
 * different question about the same thing. Never "new to you" (only what this app saw), never
 * "mastered", and follow-ups you answered stay beside this question's answers with their own
 * scores, never combined.
 */
export function FollowUpCard({ track, questionId, userId, latestAnswerId, answeredCount }: {
  track: string; questionId: string; userId: string; latestAnswerId: string | null; answeredCount: number;
}) {
  const q = useQuery<FollowUpOut>({
    queryKey: ["me", "follow-up", track, questionId, answeredCount],
    queryFn: () => api.followUp(track, questionId),
    enabled: answeredCount > 0,
  });
  const [dismissed, setDismissed] = useState<string[]>(() => readDismissed(userId));
  if (!q.data) return null;
  const data = q.data;
  const offers = data.offers.filter((o) => !dismissed.includes(dismissKey(track, questionId, o.question_id)));
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
            <Button size="sm" variant="ghost" onClick={() => {
              const next = [...dismissed, dismissKey(track, questionId, o.question_id)];
              setDismissed(next);
              writeDismissed(userId, next);
            }}>Not now</Button>
          </span>
        </div>
      ))}
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

const dismissKey = (track: string, from: string, to: string) => `${track}/${from}>${to}`;
const storageKey = (userId: string) => `codecoach.followups.dismissed.v1.${userId}`;

function readDismissed(userId: string): string[] {
  try {
    const raw = window.localStorage.getItem(storageKey(userId));
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string").slice(0, 200) : [];
  } catch {
    return [];
  }
}

function writeDismissed(userId: string, keys: string[]) {
  try {
    window.localStorage.setItem(storageKey(userId), JSON.stringify(keys.slice(-200)));
  } catch {
    /* storage refused: the offer is just hidden for this visit */
  }
}
