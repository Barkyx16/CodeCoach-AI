import { useId, useState } from "react";

import { ApiError } from "@/api/client";
import { failureKind, type FailureKind } from "@/lib/errors";

import type { ReportedError } from "./report";

/** The failure as identifiers only: the app's name for the action, its kind, code, status and request id. Never its message. */
export function reportedError(error: unknown, action: string): ReportedError {
  const api = error instanceof ApiError ? error : null;
  return { action, category: failureKind(error), code: api?.code ?? null, status: api?.status ?? null, request_id: api?.requestId ?? null };
}

/** Kinds where a report helps: not a form to correct, not a sign-in to redo. */
const HELPFUL: FailureKind[] = ["offline", "busy", "unavailable", "server", "forbidden", "other"];
export const reportHelps = (error: unknown) => !!error && HELPFUL.includes(failureKind(error));

/**
 * "Get help with this" next to a failure. The report opens in place, under the message, so the
 * learner's typed work on the page stays where it is. A new failure closes it (its report would
 * describe the old one).
 */
export function useGetHelp(error: unknown) {
  const [openFor, setOpenFor] = useState<unknown>(null);
  const panelId = useId();
  const open = !!error && openFor === error;
  return {
    open,
    panelId,
    button: {
      "aria-expanded": open,
      "aria-controls": open ? panelId : undefined,
      onClick: () => setOpenFor(open ? null : error),
      children: open ? "Hide the support report" : "Get help with this",
    },
  };
}
