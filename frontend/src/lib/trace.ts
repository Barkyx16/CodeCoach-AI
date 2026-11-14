/**
 * W3C trace context for one user action (see backend app/tracing.py and docs/OBSERVABILITY.md).
 * The browser starts the trace when the learner acts; the API continues it, so what the page saw
 * and what the server did can be read together by trace id.
 */
export interface TraceContext {
  traceId: string; // 32 hex
  spanId: string; // 16 hex: the browser's span, the parent of the server's
  traceparent: string;
}

function hex(bytes: number): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(bytes)), (b) => b.toString(16).padStart(2, "0")).join("");
}

export function newTrace(): TraceContext {
  const traceId = hex(16);
  const spanId = hex(8);
  return { traceId, spanId, traceparent: `00-${traceId}-${spanId}-01` };
}
