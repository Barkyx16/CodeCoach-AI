import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import { invalidateActionViews } from "@/api/queries";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";

/**
 * Accept one improvement from an interview review as an action (docs/ACCEPTED_ACTIONS.md). The
 * suggestion is the identity: pressing it again, here or in another tab, or after a lost reply,
 * returns the same action, never a second one. Accepting changes nothing about the review itself.
 */
export function AcceptImprovement({ interviewId, improvementKey, actionId, title }: {
  interviewId: string;
  improvementKey: string;
  actionId: string | null | undefined;
  title: string;
}) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [accepted, setAccepted] = useState<string | null>(null);
  const [weekly, setWeekly] = useState(false);
  const id = actionId ?? accepted;
  if (!improvementKey) return null;
  if (id) {
    return (
      <p className="review__accepted" role="status">
        Accepted as an action. <Link to="/plan#accepted-actions">See it on your plan</Link>, where you can schedule it.
      </p>
    );
  }
  return (
    <span className="row">
      <Button size="sm" loading={busy} aria-label={`Accept as an action: ${title}`} onClick={async () => {
        setBusy(true);
        setError(null);
        try {
          const a = await api.acceptAction({ source: { kind: "interview_improvement", interview_id: interviewId, key: improvementKey }, recurrence: weekly ? "weekly" : "once" });
          setAccepted(a.id);
          invalidateActionViews(qc);
        } catch (e) {
          setError(e);
        } finally {
          setBusy(false);
        }
      }}>Accept as an action</Button>
      <label className="checkbox">
        <input type="checkbox" checked={weekly} onChange={(e) => setWeekly(e.target.checked)} />
        Every week
      </label>
      <InlineError error={error} />
    </span>
  );
}
