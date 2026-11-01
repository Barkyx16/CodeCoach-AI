import type { ReactNode } from "react";

import { describeError } from "@/lib/errors";

import { Button } from "./Button";
import { Spinner } from "./Spinner";

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

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="state state--empty">
      <strong>{title}</strong>
      {children && <div className="muted">{children}</div>}
      {action}
    </div>
  );
}

export function InlineError({ error }: { error: unknown }) {
  if (!error) return null;
  return <p className="inline-error" role="alert">{describeError(error).message}</p>;
}
