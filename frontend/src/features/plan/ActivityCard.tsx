import { Link } from "react-router-dom";

import type { PlanItem } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { InlineError } from "@/components/States";
import { usePlanItemAction } from "@/api/queries";

import { useStartActivity } from "./useStartActivity";

const KIND_LABEL: Record<PlanItem["kind"], string> = {
  assessment: "Baseline",
  question: "Answer a question",
  retry: "Retry a weak answer",
  review: "Review feedback",
  voice: "Voice practice",
  mock: "Mock interview",
  coding: "Coding problem",
};

const STATUS_LABEL: Record<PlanItem["status"], string> = {
  pending: "Open",
  done: "Done",
  skipped: "Skipped",
  replaced: "Swapped out",
};

/** One plan activity: what, why, which skill, how long, what counts as done, and controls. */
export function ActivityCard({ item, headingLevel = 3, compact = false }: { item: PlanItem; headingLevel?: 2 | 3; compact?: boolean }) {
  const start = useStartActivity();
  const action = usePlanItemAction();
  const H = headingLevel === 2 ? "h2" : "h3";
  const open = item.status === "pending";
  return (
    <article className={`activity-card activity-card--${item.status}${compact ? " activity-card--compact" : ""}`} aria-labelledby={`act-${item.id}`}>
      <div className="row activity-card__meta">
        <Badge tone={item.status === "done" ? "success" : "neutral"}>{KIND_LABEL[item.kind]}</Badge>
        <span className="subtle"><Icon name="clock" size={13} /> about {item.minutes} min</span>
        <span className="subtle">Skill: {item.skill}</span>
        {!open && <span className="activity-card__status">{STATUS_LABEL[item.status]}{item.evidence ? `: ${item.evidence}` : ""}</span>}
      </div>
      <H className="activity-card__title" id={`act-${item.id}`}>{item.title}</H>
      <p className="activity-card__why"><span className="activity-card__label">Why:</span> {item.reason}</p>
      {!compact && <p className="subtle"><span className="activity-card__label">Done when:</span> {item.completion}</p>}
      {open && (
        <div className="row activity-card__actions">
          {item.href ? (
            <Link className="btn btn--primary btn--md" to={item.href} state={{ from: "/dashboard", fromLabel: "Back to your plan" }}>
              Start <Icon name="arrow" size={15} />
            </Link>
          ) : (
            <Button variant="primary" loading={start.pending} onClick={() => void start.open(item)}>Start <Icon name="arrow" size={15} /></Button>
          )}
          {item.can_mark_reviewed && (
            <Button variant="secondary" loading={action.isPending && action.variables?.action === "reviewed"}
              onClick={() => action.mutate({ id: item.id, action: "reviewed" })}>I've reviewed it</Button>
          )}
          {item.can_replace && (
            <Button variant="ghost" loading={action.isPending && action.variables?.action === "replace"}
              onClick={() => action.mutate({ id: item.id, action: "replace" })}>Swap for another</Button>
          )}
          <Button variant="ghost" loading={action.isPending && action.variables?.action === "skip"}
            onClick={() => action.mutate({ id: item.id, action: "skip" })}>Skip for now</Button>
        </div>
      )}
      {start.activeId && (
        <p className="banner banner--warning" role="alert">You already have an interview in progress. <Link to={`/interviews/${start.activeId}`}>Resume it</Link> first.</p>
      )}
      <InlineError error={start.error ?? action.error} />
    </article>
  );
}
