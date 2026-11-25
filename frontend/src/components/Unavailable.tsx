import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "./States";

/** Pages that can't show a record use `isGone` (lib/errors.ts) to choose these over Try again. */
type Destination = { to: string; label: string };

/** A short heading, one explanation, and a few working ways forward (the first is the main one). */
export function UnavailableState({ title, children, actions }: { title: string; children: ReactNode; actions: Destination[] }) {
  return (
    <div className="page">
      <EmptyState pageTitle title={title} action={
        <span className="row">
          {actions.map((a, i) => (
            <Link key={a.to} className={`btn ${i === 0 ? "btn--primary" : "btn--secondary"} btn--md`} to={a.to}>{a.label}</Link>
          ))}
        </span>
      }>
        {children}
      </EmptyState>
    </div>
  );
}

/**
 * A private record (a note, an application, an interview…): the same words whether it was
 * deleted, never existed, or belongs to another account, so nothing says which. Leads to the
 * learner's own list of that kind, and the dashboard.
 */
export function PrivateUnavailable({ what, list }: { what: string; list: Destination }) {
  return (
    <UnavailableState title={`This ${what} isn't available`} actions={[list, { to: "/dashboard", label: "Dashboard" }]}>
      <p>It may have been deleted, the link may be mistyped, or it may belong to a different account. Nothing was changed.</p>
    </UnavailableState>
  );
}
