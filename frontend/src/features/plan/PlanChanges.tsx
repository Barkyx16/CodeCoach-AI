import { useState } from "react";

import type { Plan } from "@/api/types";
import { Button } from "@/components/Button";

const key = (track: string) => `codecoach.plan.seen.${track}`;

function seen(track: string): number {
  try {
    return Number(window.localStorage.getItem(key(track))) || 0;
  } catch {
    return 0;
  }
}

/** "Your plan changed": the reasons behind a new plan version, until dismissed. */
export function PlanChanges({ plan, always = false }: { plan: Plan; always?: boolean }) {
  const [dismissed, setDismissed] = useState(() => seen(plan.track));
  if (!always && (plan.version <= 1 || dismissed >= plan.version)) return null;
  return (
    <div className="plan-changes" role="status">
      <strong>{plan.version > 1 ? "Your plan changed" : "Your starter plan"}</strong>
      <ul className="mini-list">{plan.changes.map((c) => <li key={c}>{c}</li>)}</ul>
      {!always && (
        <Button size="sm" variant="ghost" onClick={() => {
          try { window.localStorage.setItem(key(plan.track), String(plan.version)); } catch { /* not remembered */ }
          setDismissed(plan.version);
        }}>Got it</Button>
      )}
    </div>
  );
}
