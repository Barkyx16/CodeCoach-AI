import { useState } from "react";
import { Link } from "react-router-dom";

import { usePlan, useReviewQueue, useSaveGoals } from "@/api/queries";
import { Button } from "@/components/Button";
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

/**
 * "Today's practice": one recommendation sized to the time you have, with a support rail beside
 * it (this week's planned minutes, and the optional goal setup). The time chosen is a budget; the
 * session estimate is what the plan actually holds, and both are shown under their own names.
 */
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

  const today = plan.data?.today;
  const progress = plan.data?.progress;
  const due = reviews.data?.due.length ?? 0;
  return (
    <section className="today" aria-labelledby="today-title">
      <div className="today__head">
        <h2 className="today__title" id="today-title">Today's practice</h2>
        <fieldset className="segmented">
          <legend className="segmented__legend">Time available</legend>
          <div className="segmented__options">
            {OPTIONS.map((m) => (
              <label key={m} className={`segmented__option${minutes === m ? " is-selected" : ""}`}>
                <input type="radio" name="today-minutes" value={m} checked={minutes === m} onChange={() => choose(m)} />
                {m} min
              </label>
            ))}
          </div>
        </fieldset>
      </div>
      {plan.isPending ? <LoadingState label="Planning your session…" /> : plan.isError ? (
        <ErrorState error={plan.error} onRetry={() => void plan.refetch()} />
      ) : (
        <div className="today__grid">
          <div className="today__main">
            <PlanChanges plan={plan.data} />
            {today!.note && <p className="subtle today__note">{today!.note}</p>}
            {today!.primary ? (
              <div className="today__card">
                <ActivityCard item={today!.primary} featured />
                {/* Beside the recommendation, not inside it: the follow-up has its own actions. */}
                <div className="today__card-footer">
                  {today!.follow_up ? (
                    <details className="today__follow">
                      <summary>Next: {today!.follow_up.title} · About {today!.follow_up.minutes} min</summary>
                      <ActivityCard item={today!.follow_up} compact />
                    </details>
                  ) : <span />}
                  <span className="today__estimate">Session estimate: about {today!.session_minutes} min</span>
                </div>
              </div>
            ) : <p className="today__empty">Nothing open right now. Your plan refreshes as you practise.</p>}
          </div>
          <div className="today__rail">
            <section className="rail-card" aria-labelledby="week-title">
              <h3 className="rail-card__eyebrow" id="week-title">This week</h3>
              <p className="rail-card__metric">
                <span className="rail-card__value">{progress!.minutes_this_week}</span>
                <span className="subtle"> / {progress!.weekly_minutes} min planned</span>
              </p>
              <span className="stat__bar" aria-hidden="true">
                <span style={{ width: `${progress!.weekly_minutes ? Math.min(progress!.minutes_this_week / progress!.weekly_minutes, 1) * 100 : 0}%` }} />
              </span>
              <p className="subtle rail-card__detail">
                {progress!.done_this_week} {progress!.done_this_week === 1 ? "activity" : "activities"} completed
                {plan.data.days_to_interview !== null && plan.data.days_to_interview !== undefined ? ` · ${plan.data.days_to_interview} days to your interview` : ""}
              </p>
              <p className="rail-card__links">
                {due > 0 && <Link to="/reviews">{due} due for review</Link>}
                <Link to="/plan">Your full plan <span aria-hidden="true">→</span></Link>
              </p>
            </section>
            {!plan.data.goals_saved && (
              <section className="rail-card" aria-labelledby="goals-title">
                <h3 className="rail-card__title" id="goals-title">Make the plan yours</h3>
                <p className="subtle">Add your goals and interview date. Optional.</p>
                <div className="rail-card__actions">
                  <Link to="/plan/goals" className="rail-card__link">Set my goals <span aria-hidden="true">→</span></Link>
                  <Button size="sm" variant="ghost" aria-label="Not now, use a starter plan" loading={saveGoals.isPending}
                    onClick={() => saveGoals.mutate({ setup_skipped: true, focus_areas: [], formats: [], confidence: {} })}>
                    Not now
                  </Button>
                </div>
              </section>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
