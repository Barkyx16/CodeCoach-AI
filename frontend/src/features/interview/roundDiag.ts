import { useEffect } from "react";

import { ApiError } from "@/api/client";
import type { Interview } from "@/api/types";
import { diag } from "@/lib/diagnostics";
import { newTrace } from "@/lib/trace";
import { reportUiEvent, type UiAction, type UiOutcome } from "@/lib/uiTelemetry";

/** What a live round shows right now (for diagnostics and for choosing what to render). */
export type RoundView = "question" | "followup" | "empty" | "results";

/** How long after a saved action the next state must be on screen before it counts as not shown. */
export const RENDER_DEADLINE_MS = 5000;

function where(iv: Interview) {
  return {
    status: iv.status,
    current: iv.questions.find((q) => q.status === "current")?.index ?? null,
    pending: iv.round_format?.pending_followup?.question_index ?? null,
  };
}

// What each interview's screen shows now, updated after each render that changes it.
const onScreen = new Map<string, string>();
const watchers = new Set<(interviewId: string) => void>();

/** Called after a render that changed what an interview's screen shows. */
export function screenChanged(interviewId: string, signature: string): void {
  if (onScreen.get(interviewId) === signature) return;
  onScreen.set(interviewId, signature);
  for (const watch of watchers) watch(interviewId);
}

function nextScreen(interviewId: string, before: string | undefined, timeoutMs: number): Promise<boolean> {
  if (onScreen.get(interviewId) !== before) return Promise.resolve(true);
  return new Promise((resolve) => {
    const watch = (id: string) => {
      if (id === interviewId && onScreen.get(id) !== before) finish(true);
    };
    const timer = setTimeout(() => finish(false), timeoutMs);
    function finish(changed: boolean) {
      clearTimeout(timer);
      watchers.delete(watch);
      resolve(changed);
    }
    watchers.add(watch);
  });
}

function report(action: UiAction, traceId: string, outcome: UiOutcome, started: number, extra: { requestId?: string | null; status?: number | null; code?: string | null } = {}) {
  const duration = performance.now() - started;
  diag("ui_outcome", { action, traceId, outcome, ms: Math.round(duration), status: extra.status ?? null, requestId: extra.requestId ?? null });
  reportUiEvent({
    trace_id: traceId, action, outcome, duration_ms: duration,
    request_id: extra.requestId ?? null, status: extra.status ?? null, error_code: extra.code ?? null,
  });
}

/**
 * Run one round action as a traced user action: it gets its own trace (sent as `traceparent`), and
 * how it ended on screen is recorded: rendered (the next state appeared), rejected / server_error
 * (the server said no, or failed), network_error (no answer arrived), or not_rendered (the server
 * saved it but the screen didn't change within RENDER_DEADLINE_MS). Ids, codes and timings only.
 */
export async function tracedRoundAction(
  action: UiAction,
  interviewId: string,
  index: number,
  run: (traceparent: string) => Promise<Interview>,
): Promise<Interview> {
  const trace = newTrace();
  const started = performance.now();
  const before = onScreen.get(interviewId);
  diag("round_action", { action, interviewId, index, phase: "start", traceId: trace.traceId });
  let iv: Interview;
  try {
    iv = await run(trace.traceparent);
  } catch (error) {
    const api = error instanceof ApiError ? error : null;
    const offline = !api || api.status === 0;
    diag("round_action", {
      action, interviewId, index, phase: "error", traceId: trace.traceId,
      code: api?.code ?? "unknown", httpStatus: api?.status ?? null, requestId: api?.requestId ?? null,
    });
    report(action, trace.traceId, offline ? "network_error" : api.status >= 500 ? "server_error" : "rejected", started, {
      requestId: api?.requestId, status: api?.status ?? 0, code: api && !offline ? api.code : null,
    });
    throw error;
  }
  diag("round_action", { action, interviewId, index, phase: "done", traceId: trace.traceId, ...where(iv) });
  void nextScreen(interviewId, before, RENDER_DEADLINE_MS).then((shown) =>
    report(action, trace.traceId, shown ? "rendered" : "not_rendered", started, { status: 200 }));
  return iv;
}

/** A click the answer box didn't act on although nothing was visibly being sent. */
export function reportIgnored(action: UiAction): void {
  const trace = newTrace();
  report(action, trace.traceId, "ignored", performance.now());
}

/** Record each change of what the round shows. */
export function useRoundViewDiag(iv: Interview, view: RoundView): void {
  const { status, current, pending } = where(iv);
  useEffect(() => {
    diag("round_view", { interviewId: iv.id, view, status, current, pending });
    screenChanged(iv.id, `${view}:${status}:${current}:${pending}`);
  }, [iv.id, view, status, current, pending]);
}

/** For tests. */
export function resetRoundScreensForTests(): void {
  onScreen.clear();
  watchers.clear();
}
