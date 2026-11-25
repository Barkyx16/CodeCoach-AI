import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import type { Plan } from "@/api/types";
import { Button } from "@/components/Button";
import { dismissalsKey, planChangeKey, useDismissals } from "@/features/dismissals/dismissals";

/** "Your plan changed": the reasons behind a new plan version, until dismissed. "Got it" is kept with
 * the account for that version (docs/FOLLOW_UPS.md, "Not now"), so another device doesn't show it
 * again, and Settings can show it again. */
export function PlanChanges({ plan, always = false }: { plan: Plan; always?: boolean }) {
  const queryClient = useQueryClient();
  const key = planChangeKey(plan.track, plan.version);
  const dismissals = useDismissals(!always && plan.version > 1);
  const [gotIt, setGotIt] = useState(false);
  const save = useMutation({
    mutationFn: () => api.dismiss([{ key, offered_on: "/plan" }]),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: dismissalsKey }),
  });
  if (!always) {
    if (plan.version <= 1 || gotIt) return null;
    // Until the account's dismissals are read, nothing (no flash); if they can't be read, it shows.
    if (dismissals.isPending) return null;
    if (dismissals.data?.items.some((d) => d.key === key)) return null;
  }
  return (
    <div className="plan-changes" role="status">
      <strong>{plan.version > 1 ? "Your plan changed" : "Your starter plan"}</strong>
      <ul className="mini-list">{plan.changes.map((c) => <li key={c}>{c}</li>)}</ul>
      {(plan.read_submissions ?? []).length > 0 && (
        // The judged code the update that made this version read, as the version recorded it (Volume 16, prompt 7).
        <>
          <p className="subtle">Code this update read as new evidence:</p>
          <ul className="mini-list" aria-label="Code this update read">
            {(plan.read_submissions ?? []).map((r) => (
              <li key={r.id}>
                {r.href && r.title
                  ? <Link to={r.href}>{r.exercise ? "Debugging exercise" : "Submission"}: {r.title}</Link>
                  : "A submission that's no longer stored"}
                {r.verdict && <span className="subtle"> · {r.verdict}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      {(plan.read_lessons ?? []).length > 0 && (
        // The lesson checks the update read, by unit and version (Volume 17, prompt 3).
        <>
          <p className="subtle">Lesson checks this update read as new evidence:</p>
          <ul className="mini-list" aria-label="Lesson checks this update read">
            {(plan.read_lessons ?? []).map((r) => (
              <li key={`${r.unit_id}-${r.version}`}>
                {r.href && r.title ? <Link to={r.href}>{r.title}</Link> : "A lesson that's no longer offered"}
                <span className="subtle"> · check passed on version {r.version}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {!always && (
        <Button size="sm" variant="ghost" onClick={() => { setGotIt(true); save.mutate(); }}>Got it</Button>
      )}
    </div>
  );
}
