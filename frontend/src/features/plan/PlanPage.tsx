import { Link } from "react-router-dom";

import { usePlan } from "@/api/queries";
import type { Plan } from "@/api/types";
import { Card } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/States";
import { AcceptedActions } from "@/features/actions/AcceptedActions";

import { ActivityCard } from "./ActivityCard";
import { PlanChanges } from "./PlanChanges";

/** The whole plan: open activities, what's done (and what completed it), what was set aside, and the baseline. */
export function PlanPage() {
  const plan = usePlan(undefined, 15);
  if (plan.isPending) return <LoadingState label="Loading your plan…" />;
  if (plan.isError) return <div className="page"><ErrorState error={plan.error} onRetry={() => void plan.refetch()} /></div>;
  const p = plan.data;
  const open = p.items.filter((i) => i.status === "pending");
  const done = p.items.filter((i) => i.status === "done");
  const aside = p.items.filter((i) => i.status === "skipped" || i.status === "replaced");
  return (
    <div className="page plan-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">YOUR PRACTICE PLAN · {p.career_title.toUpperCase()}</p>
          <h1 className="page__title">Your plan</h1>
          <p className="page__subtitle">Version {p.version}. It updates when you complete work or change your goals, and says why.</p>
        </div>
        <div className="row">
          <Link to="/reviews" className="btn btn--ghost btn--md">Review queue</Link>
          <Link to="/plan/goals" state={{ from: "/plan", fromLabel: "Back to your plan" }} className="btn btn--secondary btn--md">{p.goals_saved ? "Edit goals" : "Set goals"}</Link>
          <Link to="/dashboard" className="btn btn--primary btn--md">Today</Link>
        </div>
      </div>
      <PlanChanges plan={p} always />
      <div className="plan-page__layout">
        <div className="stack">
          <section className="stack" aria-labelledby="open-title">
            <h2 className="section-title" id="open-title">Up next ({open.length})</h2>
            {open.length === 0 ? <p className="subtle">Nothing open. Your next plan appears as you practise.</p>
              : open.map((i) => <ActivityCard key={i.id} item={i} />)}
          </section>
          {done.length > 0 && (
            <section className="stack" aria-labelledby="done-title">
              <h2 className="section-title" id="done-title">Done in this version ({done.length})</h2>
              {done.map((i) => <ActivityCard key={i.id} item={i} compact />)}
            </section>
          )}
          {aside.length > 0 && (
            <section className="stack" aria-labelledby="aside-title">
              <h2 className="section-title" id="aside-title">Set aside ({aside.length})</h2>
              <p className="subtle">Skipped or swapped activities aren't counted as done, and won't come straight back.</p>
              {aside.map((i) => <ActivityCard key={i.id} item={i} compact />)}
            </section>
          )}
        </div>
        <aside className="stack">
          <AcceptedActions />
          <Assessment plan={p} />
        </aside>
      </div>
    </div>
  );
}

function Assessment({ plan }: { plan: Plan }) {
  const a = plan.assessment;
  return (
    <Card className="stack assessment">
      <h2 className="section-title">Where you are</h2>
      <p className={a.state === "building_baseline" ? "banner banner--info" : "subtle"}>{a.note}</p>
      <section aria-labelledby="self-title">
        <h3 className="assessment__h" id="self-title">What you told us</h3>
        {a.self_reported.length === 0 ? <p className="subtle">No self-ratings yet. You can add them in your goals.</p> : (
          <ul className="mini-list">{a.self_reported.map((r) => <li key={r.skill}>{r.skill}: {r.rating} of 5 (your confidence)</li>)}</ul>
        )}
      </section>
      <section aria-labelledby="eval-title">
        <h3 className="assessment__h" id="eval-title">How your answers scored</h3>
        {a.evaluated.length === 0 ? <p className="subtle">Not evaluated yet: answer a question to see rubric scores.</p> : (
          <table className="data-table">
            <thead><tr><th scope="col">Skill</th><th scope="col">Questions</th><th scope="col">Avg best score</th></tr></thead>
            <tbody>{a.evaluated.map((e) => <tr key={e.skill}><td>{e.skill}</td><td>{e.questions}</td><td>{e.average_best_score}/100</td></tr>)}</tbody>
          </table>
        )}
        <p className="subtle">Rubric scores measure how much of what interviewers listen for your answer covered. They don't say an answer is correct.</p>
      </section>
      {a.coding && (
        <section aria-labelledby="code-title">
          <h3 className="assessment__h" id="code-title">Code the judge ran</h3>
          {a.coding.judge_available
            ? <p>{a.coding.passed} passed of {a.coding.judged_attempts} judged {a.coding.judged_attempts === 1 ? "attempt" : "attempts"}.</p>
            : <p>The code judge isn't available on this server, so {a.coding.saved_not_judged} saved {a.coding.saved_not_judged === 1 ? "attempt has" : "attempts have"} no verdict. Correctness only ever comes from the judge.</p>}
        </section>
      )}
    </Card>
  );
}
