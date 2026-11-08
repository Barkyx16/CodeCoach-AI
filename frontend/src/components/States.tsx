import type { ReactNode } from "react";

import { reportedError, reportHelps, useGetHelp } from "@/features/support/getHelp";
import { SupportReportPanel } from "@/features/support/SupportReport";
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

/**
 * A page (or a section of one) that couldn't load. Where a support report could help (no reply, a
 * service down, a fault on our side), "Get help with this" opens one here; `action` names what
 * failed in the report, in the app's words.
 */
export function ErrorState({ error, onRetry, action = "Loading this page" }: { error: unknown; onRetry?: () => void; action?: string }) {
  const { title, message, requestId } = describeError(error);
  const offline = typeof navigator !== "undefined" && !navigator.onLine && (error as { code?: string } | null)?.code === "network_error";
  const help = useGetHelp(error);
  const helps = reportHelps(error);
  return (
    <div className="state state--error">
      <div role="alert" className="stack-sm state__message">
        <strong>{title}</strong>
        <p className="muted">{message}</p>
        {requestId && <p className="subtle">Reference: <code>{requestId}</code></p>}
        {offline && <p className="muted">You're offline. This page isn't saved on this device; <a href="/offline">see what is</a>.</p>}
      </div>
      {(onRetry || helps) && (
        <div className="row state__actions">
          {onRetry && <Button onClick={onRetry}>Try again</Button>}
          {helps && <Button variant="ghost" {...help.button} />}
        </div>
      )}
      {help.open && (
        <div id={help.panelId} className="state__report">
          <SupportReportPanel problem={reportedError(error, action)} />
        </div>
      )}
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

/**
 * An error under a form. Give it an `id` and point the field's aria-describedby at it so the field
 * says what's wrong. With `action` (what failed, in the app's words: "Saving your answer"), a
 * failure a support report could help with also offers "Get help with this", opened in place.
 */
export function InlineError({ error, id, action }: { error: unknown; id?: string; action?: string }) {
  const help = useGetHelp(error);
  if (!error) return null;
  const message = <p className="inline-error" role="alert" id={id}>{describeError(error).message}</p>;
  if (!action || !reportHelps(error)) return message;
  return (
    <div className="inline-error__group stack-sm">
      {message}
      <span><Button size="sm" variant="ghost" {...help.button} /></span>
      {help.open && <div id={help.panelId}><SupportReportPanel problem={reportedError(error, action)} /></div>}
    </div>
  );
}
