import { useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { usePlan } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { Icon } from "@/components/Icon";

import { forgetPlanOrigin, planOriginFor } from "./planOrigin";
import { savedMinutes } from "./todayMinutes";

/**
 * On a page opened from the plan: says so, and once the server has counted the activity as done
 * (from its own evidence; opening the page or reading feedback doesn't count), names the plan's
 * next step and leads back to it. Shown only for the account and tab that opened it.
 */
export function PlanReturn() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const [dismissed, setDismissed] = useState<string | null>(null);
  const origin = planOriginFor(user?.id, pathname);
  const show = origin !== null && dismissed !== origin.itemId;
  const plan = usePlan(undefined, savedMinutes(), show);
  if (!show || !origin) return null;

  const p = plan.data;
  const item = p?.items.find((i) => i.id === origin.itemId);
  const done = item?.status === "done" || (p?.changes.some((c) => c.startsWith(`Done: “${origin.title}”`)) ?? false);
  const next = p?.today.primary && p.today.primary.title !== origin.title ? p.today.primary : null;
  const back = origin.from === "/plan" ? "Back to your plan" : "Back to your dashboard";

  return (
    <aside className={`plan-return focus-hide${done ? " plan-return--done" : ""}`} aria-label="From your plan">
      <span className="plan-return__icon" aria-hidden="true"><Icon name={done ? "check" : "target"} size={16} /></span>
      <p className="plan-return__text" role="status">
        {done ? (
          <>
            <strong>Done for your plan:</strong> {origin.title}.{" "}
            {next ? <>Next: {next.title} (about {next.minutes} min).</> : p ? "Nothing else is open in your plan right now." : null}
          </>
        ) : (
          <>
            <strong>From your plan:</strong> {origin.title}.
            {item?.completion ? <> Done when: {item.completion}</> : null}
          </>
        )}
      </p>
      <Link className="plan-return__link" to={origin.from}>{done && next ? "Continue your plan" : back} <span aria-hidden="true">→</span></Link>
      <button type="button" className="plan-return__close" aria-label="Hide this note"
        onClick={() => { forgetPlanOrigin(); setDismissed(origin.itemId); }}>
        <span aria-hidden="true">×</span>
      </button>
    </aside>
  );
}
