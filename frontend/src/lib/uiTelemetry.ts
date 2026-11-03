/**
 * How round actions ended on screen, reported to this app's own API (POST /api/v1/telemetry/ui)
 * when the server allows it (capabilities.ui_telemetry). Outcome, timing, trace and request ids
 * only: never answers, page content or other ids.
 *
 * Best effort by design: events are batched, at most one batch is in flight, nothing is retried,
 * and a failure drops the batch. Telemetry can never slow down, break or sign out of practice.
 */
import { apiRequest } from "@/api/client";

export type UiAction = "answer" | "skip" | "reply" | "skip_followup";
export type UiOutcome = "rendered" | "rejected" | "server_error" | "network_error" | "not_rendered" | "ignored";

export interface UiEvent {
  trace_id: string;
  action: UiAction;
  outcome: UiOutcome;
  duration_ms: number;
  request_id?: string | null;
  status?: number | null;
  error_code?: string | null;
}

const MAX_QUEUE = 50;
const MAX_BATCH = 20;
const FLUSH_DELAY_MS = 2000;

let enabled = false;
let queue: UiEvent[] = [];
let timer: ReturnType<typeof setTimeout> | null = null;
let inFlight = false;
export const telemetryStats = { sent: 0, dropped: 0, failedBatches: 0 };

/** Follow the server's capability flag; off clears anything waiting. */
export function setUiTelemetryEnabled(on: boolean): void {
  enabled = on;
  if (!on) {
    queue = [];
    if (timer) clearTimeout(timer);
    timer = null;
  }
}

export function reportUiEvent(event: UiEvent): void {
  if (!enabled) return;
  if (queue.length >= MAX_QUEUE) {
    telemetryStats.dropped += 1; // a burst: keep the earliest, drop the rest
    return;
  }
  queue.push({ ...event, duration_ms: Math.max(0, Math.min(600_000, Math.round(event.duration_ms))) });
  if (queue.length >= MAX_BATCH) void flushUiTelemetry();
  else if (!timer) timer = setTimeout(() => void flushUiTelemetry(), FLUSH_DELAY_MS);
}

/** Send what's waiting (one batch). `keepalive` lets it finish while the page unloads. */
export async function flushUiTelemetry(keepalive = false): Promise<void> {
  if (timer) clearTimeout(timer);
  timer = null;
  if (!enabled || inFlight || queue.length === 0) return;
  const batch = queue.splice(0, MAX_BATCH);
  inFlight = true;
  try {
    await apiRequest<void>("/api/v1/telemetry/ui", { method: "POST", body: { events: batch }, keepalive, noRefresh: true });
    telemetryStats.sent += batch.length;
  } catch {
    telemetryStats.failedBatches += 1; // dropped, never retried: no retry storm
    telemetryStats.dropped += batch.length;
  } finally {
    inFlight = false;
  }
  if (queue.length) timer = setTimeout(() => void flushUiTelemetry(), FLUSH_DELAY_MS);
}

if (typeof window !== "undefined") {
  window.addEventListener("pagehide", () => void flushUiTelemetry(true));
}

/** For tests. */
export function resetUiTelemetryForTests(): void {
  setUiTelemetryEnabled(false);
  inFlight = false;
  telemetryStats.sent = telemetryStats.dropped = telemetryStats.failedBatches = 0;
}
