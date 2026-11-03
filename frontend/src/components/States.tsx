import type { ReactNode } from "react";

import { describeError } from "@/lib/errors";

import { Button } from "./Button";
import { Spinner } from "./Spinner";
import { Icon } from "./Icon";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state state--loading">
      <Spinner label={label} />
      <span className="muted">{label}</span>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { title, message, requestId } = describeError(error);
  return (
    <div className="state state--error" role="alert">
      <strong>{title}</strong>
      <p className="muted">{message}</p>
      {requestId && <p className="subtle">Reference: <code>{requestId}</code></p>}
      {onRetry && <Button onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function EmptyState({ title, children, action, pageTitle = false }: {
  title: string; children?: ReactNode; action?: ReactNode;
  /** Render the title as the page's <h1> (for pages that are only an empty state, like 404). */
  pageTitle?: boolean;
}) {
  return (
    <div className="state state--empty">
      <span className="state__icon"><Icon name="book" size={22} /></span>
      {pageTitle ? <h1 className="state__title">{title}</h1> : <strong>{title}</strong>}
      {children && <div className="muted">{children}</div>}
      {action}
    </div>
  );
}

/** An error under a form. Give it an `id` and point the field's aria-describedby at it so the field says what's wrong. */
export function InlineError({ error, id }: { error: unknown; id?: string }) {
  if (!error) return null;
  return <p className="inline-error" role="alert" id={id}>{describeError(error).message}</p>;
}
