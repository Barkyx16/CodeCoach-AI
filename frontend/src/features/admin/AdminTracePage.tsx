import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import type { TraceOut, TraceSpan } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { ErrorState, LoadingState } from "@/components/States";

const OK = new Set(["ok", "rendered"]);
const tone = (outcome: string) => (OK.has(outcome) ? "success" : outcome === "rejected" ? "warning" : "danger");

/** Server spans as a tree: each under its parent, in start order. */
function tree(spans: TraceSpan[]): { span: TraceSpan; depth: number }[] {
  const ids = new Set(spans.map((s) => s.span_id));
  const children = new Map<string | null, TraceSpan[]>();
  for (const s of spans) {
    const parent = s.parent_id && ids.has(s.parent_id) ? s.parent_id : null;
    children.set(parent, [...(children.get(parent) ?? []), s]);
  }
  const out: { span: TraceSpan; depth: number }[] = [];
  const visit = (parent: string | null, depth: number) => {
    for (const s of (children.get(parent) ?? []).sort((a, b) => a.started_at - b.started_at)) {
      out.push({ span: s, depth });
      visit(s.span_id, depth + 1);
    }
  };
  visit(null, 0);
  return out;
}

function Trace({ trace }: { trace: TraceOut }) {
  const rows = tree(trace.spans);
  const t0 = Math.min(...trace.spans.map((s) => s.started_at), ...trace.events.map((e) => e.at));
  return (
    <div className="stack">
      <p className="subtle">Trace <code>{trace.trace_id}</code></p>
      <section className="card stack-sm" aria-labelledby="trace-server">
        <h2 className="section-title" id="trace-server">On the server</h2>
        {rows.length === 0 ? <p className="subtle">No server steps recorded for this trace.</p> : (
          <ol className="trace-spans">
            {rows.map(({ span, depth }) => (
              <li key={span.span_id} style={{ paddingInlineStart: `${depth * 1.25}rem` }}>
                <strong>{span.name}</strong> <Badge tone={tone(span.outcome)}>{span.outcome}</Badge>{" "}
                <span className="subtle">{span.duration_ms.toFixed(1)} ms · at +{Math.round((span.started_at - t0) * 1000)} ms</span>
                {Object.keys(span.attrs).length > 0 && (
                  <span className="trace-attrs subtle"> · {Object.entries(span.attrs).map(([k, v]) => `${k}=${String(v)}`).join(", ")}</span>
                )}
                {span.request_id && <span className="subtle"> · request {span.request_id}</span>}
              </li>
            ))}
          </ol>
        )}
      </section>
      <section className="card stack-sm" aria-labelledby="trace-browser">
        <h2 className="section-title" id="trace-browser">In the browser</h2>
        {trace.events.length === 0 ? <p className="subtle">The browser didn't report this action (telemetry off, or it never got that far).</p> : (
          <ul className="trace-events">
            {trace.events.map((e, i) => (
              <li key={i}>
                {e.action}: <Badge tone={tone(e.outcome)}>{e.outcome}</Badge>{" "}
                <span className="subtle">after {e.duration_ms} ms{e.status !== null ? ` · HTTP ${e.status}` : ""}{e.error_code ? ` · ${e.error_code}` : ""}{e.request_id ? ` · request ${e.request_id}` : ""}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/** Admin: look up one user action by its trace id or a request id (shown with errors). */
export function AdminTracePage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [value, setValue] = useState(id);
  const trace = useQuery({ queryKey: ["admin", "trace", id], queryFn: () => api.adminTrace(id), enabled: id.length > 0, retry: false });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const next = value.trim();
    if (next) navigate(`/admin/traces/${encodeURIComponent(next)}`);
  };
  return (
    <div className="page admin-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">ADMIN · DIAGNOSTICS</p>
          <h1 className="page__title">Trace lookup</h1>
          <p className="page__subtitle">One learner action, from the server's steps to what the browser showed. Recent traces only, kept in this server's memory; no answers or personal details are recorded.</p>
        </div>
        <div className="row dashboard__actions"><Link to="/admin/reports" className="btn btn--secondary btn--md">Reports</Link></div>
      </div>
      <form className="row" onSubmit={submit} role="search" aria-label="Find a trace">
        <label className="field" htmlFor="trace-id">
          <span className="field__label">Trace id or request id</span>
          <input id="trace-id" className="input" value={value} onChange={(e) => setValue(e.target.value)} autoComplete="off" spellCheck={false} />
        </label>
        <Button type="submit" variant="primary">Look up</Button>
      </form>
      {id && (trace.isPending ? <LoadingState label="Loading the trace…" />
        : trace.isError ? <ErrorState error={trace.error} />
        : <Trace trace={trace.data} />)}
    </div>
  );
}
