import { Link, useLocation } from "react-router-dom";

import { ScheduleLink } from "@/features/schedule/ScheduleLink";

import type { PlanItem, ScheduleEntry } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Icon, type IconName } from "@/components/Icon";
import { MoreOptions } from "@/components/MoreOptions";
import { InlineError } from "@/components/States";
import { usePlanItemAction } from "@/api/queries";

import { planReturnState, useStartActivity } from "./useStartActivity";

const KIND_LABEL: Record<PlanItem["kind"], string> = {
  assessment: "Baseline",
  question: "Answer a question",
  retry: "Retry a weak answer",
  review: "Review feedback",
  voice: "Voice practice",
  mock: "Mock interview",
  coding: "Coding problem",
  learn: "Short lesson",
};

const KIND_ICON: Record<PlanItem["kind"], IconName> = {
  assessment: "target",
  question: "file",
  retry: "spark",
  review: "list",
  voice: "mic",
  mock: "clock",
  coding: "code",
  learn: "book",
};

const STATUS_LABEL: Record<PlanItem["status"], string> = {
  pending: "Open",
  done: "Done",
  skipped: "Skipped",
  replaced: "Swapped out",
};

/**
 * One plan activity: what, why, which skill, how long, what counts as done, and controls. One
 * filled action (Start practice); "Choose another" swaps it; scheduling and skipping sit in
 * More options. `featured` is Today's recommendation.
 */
export function ActivityCard({ item, headingLevel = 3, compact = false, featured = false, scheduled = null }: {
  item: PlanItem; headingLevel?: 2 | 3; compact?: boolean; featured?: boolean;
  /** An upcoming schedule entry for this activity, if there is one: shown instead of another "Add". */
  scheduled?: ScheduleEntry | null;
}) {
  const start = useStartActivity();
  const action = usePlanItemAction();
  const { pathname } = useLocation();
  const H = headingLevel === 2 ? "h2" : "h3";
  const open = item.status === "pending";
  const variant = `${compact ? " activity-card--compact" : ""}${featured ? " activity-card--featured" : ""}`;
  return (
    <article className={`activity-card activity-card--${item.status}${variant}`} aria-labelledby={`act-${item.id}`}>
      <div className="activity-card__meta">
        <span className="activity-card__kind">
          <span className="activity-card__kind-icon" aria-hidden="true"><Icon name={KIND_ICON[item.kind]} size={14} /></span>
          {KIND_LABEL[item.kind]}
        </span>
        {item.skill !== KIND_LABEL[item.kind] && <span className="activity-card__skill"><span className="visually-hidden">Skill: </span>{item.skill}</span>}
        <span className="activity-card__time"><Icon name="clock" size={13} aria-hidden="true" /> About {item.minutes} min</span>
        {open && scheduled && <span className="activity-card__scheduled">Scheduled {whenText(scheduled)}</span>}
        {!open && <Badge tone={item.status === "done" ? "success" : "neutral"}>{STATUS_LABEL[item.status]}{item.evidence ? `: ${item.evidence}` : ""}</Badge>}
      </div>
      <H className="activity-card__title" id={`act-${item.id}`}>{item.title}</H>
      <p className="activity-card__why"><span className="visually-hidden">Why: </span>{item.reason}</p>
      {!compact && <p className="activity-card__done"><span className="activity-card__label">Done when:</span> {item.completion}</p>}
      {open && (
        <div className="activity-card__actions">
          {item.href ? (
            <Link className="btn btn--primary btn--md" to={item.href} state={planReturnState(pathname, item)}
              onClick={() => start.remember(item, item.href!)}>
              Start practice <Icon name="arrow" size={15} />
            </Link>
          ) : (
            <Button variant="primary" loading={start.pending} onClick={() => void start.open(item)}>Start practice <Icon name="arrow" size={15} /></Button>
          )}
          {item.can_mark_reviewed && (
            <Button variant="secondary" loading={action.isPending && action.variables?.action === "reviewed"}
              onClick={() => action.mutate({ id: item.id, action: "reviewed" })}>I've reviewed it</Button>
          )}
          {item.can_replace && (
            <Button variant="ghost" className="activity-card__swap" loading={action.isPending && action.variables?.action === "replace"}
              onClick={() => action.mutate({ id: item.id, action: "replace" })}>Choose another</Button>
          )}
          <MoreOptions>
            {scheduled
              ? <Link to="/schedule">Scheduled {whenText(scheduled)}: view or change</Link>
              : <ScheduleLink kind="plan_item" refId={item.id} title={item.title} />}
            <Button variant="ghost" loading={action.isPending && action.variables?.action === "skip"}
              onClick={() => action.mutate({ id: item.id, action: "skip" })}>Skip for now</Button>
          </MoreOptions>
        </div>
      )}
      {start.activeId && (
        <p className="banner banner--warning" role="alert">You already have an interview in progress. <Link to={`/interviews/${start.activeId}`}>Resume it</Link> first.</p>
      )}
      <InlineError error={start.error ?? action.error} />
    </article>
  );
}

/** "Thu 6 Nov at 09:00" (or the day alone for an all-day entry), in the learner's locale. */
function whenText(entry: ScheduleEntry): string {
  const day = new Date(`${entry.on_date}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
  return entry.local_time && !entry.all_day ? `${day} at ${entry.local_time.slice(0, 5)}` : day;
}
