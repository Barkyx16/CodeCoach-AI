import { useState } from "react";
import { Link } from "react-router-dom";

import { usePlan, useReviewQueue, useSaveGoals } from "@/api/queries";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { ErrorState, LoadingState } from "@/components/States";

import { ActivityCard } from "./ActivityCard";
import { PlanChanges } from "./PlanChanges";

const OPTIONS = [5, 15, 30] as const;
const KEY = "codecoach.today.minutes";

function savedMinutes(): number {
  try {
    const v = Number(window.localStorage.getItem(KEY));
    return (OPTIONS as readonly number[]).includes(v) ? v : 15;
  } catch {
    return 15;
  }
}

/** "Today": one next action, an optional follow-up, sized to the time you have. */
export function TodayCard() {
  const [minutes, setMinutes] = useState(savedMinutes);
  const plan = usePlan(undefined, minutes);
  const saveGoals = useSaveGoals();
  const reviews = useReviewQueue();
  const choose = (m: number) => {
    setMinutes(m);
    try {
      window.localStorage.setItem(KEY, String(m));
    } catch {
      /* not remembered */
    }
  };

  return (
    <section className="card stack today" aria-labelledby="today-title">
      <div className="today__head">
        <h2 className="section-title" id="today-title"><Icon name="target" size={16} />Today</h2>
        <fieldset className="today__time">
          <legend className="visually-hidden">How much time do you have?</legend>
          {OPTIONS.map((m) => (
            <label key={m} className={`chip${minutes === m ? " chip--active" : ""}`}>
              <input type="radio" name="today-minutes" value={m} checked={minutes === m} onChange={() => choose(m)} />
              I have {m} minutes
            </label>
          ))}
        </fieldset>
      </div>
      {plan.isPending ? <LoadingState label="Planning your session…" /> : plan.isError ? (
        <ErrorState error={plan.error} onRetry={() => void plan.refetch()} />
      ) : (
        <>
          {!plan.data.goals_saved && (
            <div className="today__setup">
              <p><strong>Want a plan that fits you?</strong> Tell us your level, focus and interview date. It takes a minute and is optional.</p>
              <div className="row">
                <Link to="/plan/goals" className="btn btn--secondary btn--sm">Set my goals</Link>
                <Button size="sm" variant="ghost" loading={saveGoals.isPending} onClick={() => saveGoals.mutate({ setup_skipped: true, focus_areas: [], formats: [], confidence: {} })}>
                  Not now, use a starter plan
                </Button>
              </div>
            </div>
          )}
          <PlanChanges plan={plan.data} />
          {plan.data.today.note && <p className="subtle today__note">{plan.data.today.note}</p>}
          {plan.data.today.primary ? (
            <>
              <ActivityCard item={plan.data.today.primary} />
              {plan.data.today.follow_up && (
                <details className="today__follow">
                  <summary>If you have time after: {plan.data.today.follow_up.title} (about {plan.data.today.follow_up.minutes} min)</summary>
                  <ActivityCard item={plan.data.today.follow_up} compact />
                </details>
              )}
            </>
          ) : <p>Nothing open right now. Your plan refreshes as you practise.</p>}
          <div className="today__foot">
            <span className="subtle">
              Session: about {plan.data.today.session_minutes} min · This week: {plan.data.progress.minutes_this_week} of {plan.data.progress.weekly_minutes} planned minutes
              ({plan.data.progress.done_this_week} {plan.data.progress.done_this_week === 1 ? "activity" : "activities"} done)
              {plan.data.days_to_interview !== null && plan.data.days_to_interview !== undefined ? ` · ${plan.data.days_to_interview} days to your interview` : ""}
            </span>
            <span className="row">
              {(reviews.data?.due.length ?? 0) > 0 && <Link to="/reviews">{reviews.data!.due.length} due for review</Link>}
              <Link to="/plan">Your full plan <span aria-hidden="true">→</span></Link>
            </span>
          </div>
        </>
      )}
    </section>
  );
}
