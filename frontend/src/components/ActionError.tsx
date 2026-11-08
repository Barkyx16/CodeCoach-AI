import { Link, useLocation } from "react-router-dom";

import { reportedError, reportHelps, useGetHelp } from "@/features/support/getHelp";
import { SupportReportPanel } from "@/features/support/SupportReport";
import { useRetryWait } from "@/hooks/useCountdown";
import { describeError, failureKind, formatWait } from "@/lib/errors";

import { Button } from "./Button";

/**
 * One failed action, shown next to its control: what didn't happen, why in the learner's terms,
 * and the way on (try again, once any wait the server asked for is over; sign in again). The
 * learner's work stays where it was: this never replaces the page.
 *
 * Only the first sentence is announced (role="alert"), once. The countdown and the button sit
 * outside it, so a ticking wait isn't read out every second. Where a support report could help,
 * "Get help with this" opens one in place (identifiers only, never the message or the work).
 */
export function ActionError({ error, action, onRetry, retrying = false, repeatSafe = false, id }: {
  error: unknown;
  /** What the learner tried, as a noun phrase: "Your submission", "The hint". */
  action: string;
  onRetry?: () => void;
  retrying?: boolean;
  /** Sending it again can't do it twice (the request has a key, or the server dedupes). */
  repeatSafe?: boolean;
  id?: string;
}) {
  const location = useLocation();
  const wait = useRetryWait(error);
  const help = useGetHelp(error);
  if (!error) return null;
  const kind = failureKind(error);
  const { message, requestId } = describeError(error);
  let detail: string;
  switch (kind) {
    case "offline":
      detail = repeatSafe
        ? "No reply came back, so we can't tell whether it arrived. Trying again is safe: it won't be done twice."
        : "CodeCoach can't be reached. Check your connection, then try again.";
      break;
    case "signed_out":
      detail = "Your session ended. Sign in again; what you've entered here is kept.";
      break;
    case "server":
      detail = "Something went wrong on our side. What you've entered here is kept.";
      break;
    default:
      detail = message;
  }
  const retryable = ["offline", "busy", "unavailable", "server", "other"].includes(kind);
  const helps = reportHelps(error);
  return (
    <div className="action-error banner banner--warning" id={id}>
      <p role="alert" className="action-error__message"><strong>{action} didn't go through.</strong> {detail}</p>
      {(wait > 0 || (onRetry && retryable) || kind === "signed_out" || (kind === "server" && requestId) || helps) && (
        <div className="action-error__actions">
          {wait > 0 && <span className="subtle">You can try again in {formatWait(wait)}.</span>}
          {onRetry && retryable && (
            <Button size="sm" onClick={onRetry} loading={retrying} disabled={wait > 0}>Try again</Button>
          )}
          {kind === "signed_out" && (
            <Link className="btn btn--secondary btn--sm" to="/login" state={{ from: location.pathname + location.search }}>
              Sign in again
            </Link>
          )}
          {kind === "server" && requestId && (
            <span className="subtle">Reference for support: <code>{requestId.slice(0, 12)}</code></span>
          )}
          {helps && <Button size="sm" variant="ghost" {...help.button} />}
        </div>
      )}
      {help.open && (
        <div id={help.panelId}>
          <SupportReportPanel problem={reportedError(error, action)} pagePath={location.pathname} />
        </div>
      )}
    </div>
  );
}
