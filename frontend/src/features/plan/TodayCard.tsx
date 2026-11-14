import { useState } from "react";
import { Link } from "react-router-dom";

import { usePlan, useReviewQueue, useSaveGoals, useSchedule } from "@/api/queries";
import type { PlanItem } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { ErrorState, LoadingState } from "@/components/States";

import { ActivityCard } from "./ActivityCard";
import { PlanChanges } from "./PlanChanges";
import { addedFor, saveAdded } from "./todayAdded";
import { saveMinutes, savedMinutes, TODAY_OPTIONS as OPTIONS } from "./todayMinutes";

const isoDay = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/**
 * "Today's practice": one recommendation sized to the time you have, with a support rail beside
 * it (estimated minutes of the last 7 days against the weekly goal, and the optional goal setup).
 * The time chosen is a maximum budget, not a target: the session estimate is what the plan holds,
 * and both are shown under their own names. With time left, the learner may add another pending
 * activity from the same plan that fits what's left; nothing is added for them, and an unused
 * minute isn't a shortfall.
 */
export function TodayCard() {
  const [minutes, setMinutes] = useState(savedMinutes);
  const plan = usePlan(undefined, minutes);
  const saveGoals = useSaveGoals();
  const reviews = useReviewQueue();
  const choose = (m: number) => {
    setMinutes(m);
    saveMinutes(m);
  };

  const { user } = useAuth();
  const now = new Date();
  const schedule = useSchedule(isoDay(now), isoDay(new Date(now.getTime() + 60 * 86_400_000)));
  const scheduledFor = (id: string) =>
    schedule.data?.find((e) => e.kind === "plan_item" && e.ref === id && e.status === "scheduled" && !e.done_at) ?? null;

  // Activities the learner chose to add today, by id, for this plan version and budget only.
  const scope = plan.data && user ? `${user.id}:${plan.data.track}:${plan.data.version}:${minutes}` : null;
  const [addedState, setAddedState] = useState<{ scope: string | null; ids: string[] }>({ scope: null, ids: [] });
  const added = scope && addedState.scope === scope ? addedState.ids : scope ? addedFor(scope) : [];
  const add = (id: string) => {
    if (!scope) return;
    const ids = [...added, id];
    saveAdded(scope, ids);
    setAddedState({ scope, ids });
  };

  const today = plan.data?.today;
  const progress = plan.data?.progress;
  const due = reviews.data?.due.length ?? 0;
  const items = plan.data?.items ?? [];
  // Added items still in this plan version (a new version after a completion starts afresh).
  const addedItems = added.map((id) => items.find((i) => i.id === id)).filter((i): i is PlanItem => i !== undefined);
  const addedMinutes = addedItems.reduce((n, i) => n + i.minutes, 0);
  const session = (today?.session_minutes ?? 0) + addedMinutes;
  const left = minutes - session;
  const inToday = new Set([today?.primary?.id, today?.follow_up?.id, ...added]);
  const candidate = items
    .filter((i) => i.status === "pending" && !inToday.has(i.id))
    .sort((a, b) => a.position - b.position)
    .find((i) => i.minutes <= left) ?? null;
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
                <ActivityCard item={today!.primary} featured scheduled={scheduledFor(today!.primary.id)} />
                {/* Beside the recommendation, not inside it: the follow-up has its own actions. */}
                <div className="today__card-footer">
                  {today!.follow_up ? (
                    <details className="today__follow">
                      <summary>Next: {today!.follow_up.title} · About {today!.follow_up.minutes} min</summary>
                      <ActivityCard item={today!.follow_up} compact scheduled={scheduledFor(today!.follow_up.id)} />
                    </details>
                  ) : <span />}
                  <span className="today__estimate">
                    Session estimate: about {session} min{addedItems.length > 0 ? ` (with ${addedItems.length} added)` : ""}
                  </span>
                </div>
              </div>
            ) : <p className="today__empty">Nothing open right now. Your plan refreshes as you practise.</p>}
            {today!.primary && addedItems.length > 0 && (
              <section className="today__added" aria-labelledby="added-title">
                <h3 className="today__added-title" id="added-title">Added for today</h3>
                {addedItems.map((i) => <ActivityCard key={i.id} item={i} compact scheduled={scheduledFor(i.id)} />)}
              </section>
            )}
            {today!.primary && left >= 5 && (
              <p className="today__topup">
                <span>About {left} of your {minutes} min left.</span>
                {candidate ? (
                  <Button size="sm" variant="secondary" onClick={() => add(candidate.id)}>
                    Add another activity ({candidate.title}, about {candidate.minutes} min)
                  </Button>
                ) : (
                  <span className="subtle">
                    Nothing else in your plan fits that, and that's fine.
                    {due > 0 && <> You could <Link to="/reviews">review {due} saved {due === 1 ? "answer" : "answers"} that {due === 1 ? "is" : "are"} due</Link>.</>}
                  </span>
                )}
              </p>
            )}
          </div>
          <div className="today__rail">
            <section className="rail-card" aria-labelledby="week-title">
              {/* A rolling 7 days of estimated minutes for finished activities (each counted once),
                  not timed practice: the label says so. */}
              <h3 className="rail-card__eyebrow" id="week-title">Last 7 days</h3>
              <p className="rail-card__metric">
                <span className="rail-card__value">{progress!.minutes_this_week}</span>
                <span className="subtle"> / {progress!.weekly_minutes} min weekly goal</span>
              </p>
              <span className="stat__bar" aria-hidden="true">
                <span style={{ width: `${progress!.weekly_minutes ? Math.min(progress!.minutes_this_week / progress!.weekly_minutes, 1) * 100 : 0}%` }} />
              </span>
              <p className="subtle rail-card__detail">
                Estimated from {progress!.done_this_week} finished {progress!.done_this_week === 1 ? "activity" : "activities"}, not timed
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
