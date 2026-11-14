import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useTestDesign, useTestRun, useTestRuns } from "@/api/queries";
import type { TestCaseIn, TestDesignExercise, TestDesignVariant } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { formatArgs, formatDateTime, formatValue } from "@/lib/format";
import { useCopySince, writeCopy } from "@/lib/deviceCopies";
import { useRequestKey } from "@/lib/requestKey";

import { type CaseRow, draftKey, LABELS, newRow, parseRow, rowFrom, signatureText } from "./cases";
import { RunReport } from "./RunReport";

export function TestDesignPage() {
  const { slug = "" } = useParams();
  const exercise = useTestDesign(slug);
  if (exercise.isPending) return <LoadingState label="Loading the exercise…" />;
  if (exercise.isError) return <div className="page"><ErrorState error={exercise.error} onRetry={() => void exercise.refetch()} /></div>;
  return <Designer key={slug} ex={exercise.data} />;
}

function readDraft(key: string): CaseRow[] | null {
  try {
    const rows = JSON.parse(localStorage.getItem(key) ?? "null") as unknown;
    return Array.isArray(rows) && rows.length ? (rows as CaseRow[]) : null;
  } catch {
    return null;
  }
}

function Designer({ ex }: { ex: TestDesignExercise }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const key = draftKey(user?.id ?? "anon", ex.slug);
  const since = useCopySince(key); // a copy removed from "Your data" after this opened isn't written back
  const [restored] = useState(() => readDraft(key));
  const [rows, setRows] = useState<CaseRow[]>(() => restored ?? [newRow(ex)]);
  const [showErrors, setShowErrors] = useState(false);
  const [serverErrors, setServerErrors] = useState<Record<string, string[]>>({});
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [variants, setVariants] = useState<TestDesignVariant[] | null>(null);
  const [status, setStatus] = useState(restored ? "Your unsent cases were restored from this device." : "");
  const run = useTestRun(runId);
  const runs = useTestRuns(ex.slug);
  const sendKey = useRequestKey();
  const focusAfter = useRef<string | null>(null);

  // Cases not yet run are kept on this device, so a reload or a closed tab loses nothing.
  useEffect(() => {
    writeCopy(key, JSON.stringify(rows), since); // blocked or removed on purpose: they last as long as the page
  }, [rows, key, since]);
  useEffect(() => {
    if (!focusAfter.current) return;
    document.getElementById(focusAfter.current)?.focus();
    focusAfter.current = null;
  });
  const finished = run.data && !["queued", "running"].includes(run.data.status);
  useEffect(() => {
    if (finished) void runs.refetch();
  }, [finished]); // eslint-disable-line react-hooks/exhaustive-deps -- once per finished run

  const parsed = rows.map((r) => parseRow(ex, r));
  const allValid = parsed.every((p) => "case" in p);
  const update = (i: number, patch: Partial<CaseRow>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const setField = (i: number, name: string, value: string) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, fields: { ...r.fields, [name]: value } } : r)));

  function add() {
    const row = newRow(ex);
    setRows((rs) => [...rs, row]);
    focusAfter.current = `${row.id}-${ex.params[0]?.name}`;
  }
  function remove(i: number) {
    const next = rows[i + 1] ?? rows[i - 1];
    setRows((rs) => rs.filter((_, j) => j !== i));
    focusAfter.current = next ? `${next.id}-${ex.params[0]?.name}` : "td-add";
    setStatus(`Case ${i + 1} removed.`);
  }

  async function send() {
    setShowErrors(true);
    setServerErrors({});
    setError(null);
    if (!allValid) {
      setStatus("Some cases need fixing first; the messages are next to the fields.");
      return;
    }
    const cases = parsed.map((p) => (p as { case: TestCaseIn }).case);
    setBusy(true);
    try {
      const out = await api.startTestRun(ex.slug, { cases, client_request_id: sendKey.keyFor([ex.slug, cases]) });
      sendKey.done();
      qc.setQueryData(["me", "test-design", "run", out.id], out);
      setRunId(out.id);
      void runs.refetch();
      setStatus(out.status === "not_run" ? out.status_detail : "Sent. The report appears below when the judge has run your cases.");
      focusAfter.current = "td-result";
    } catch (e) {
      if (e instanceof ApiError && e.code === "invalid_cases") {
        setServerErrors(((e.details as { cases?: Record<string, string[]> } | null)?.cases) ?? {});
      }
      setError(e); // the cases stay on the page and on this device
    } finally {
      setBusy(false);
    }
  }

  async function reveal() {
    try {
      setVariants(await api.testDesignVariants(ex.slug));
      setAsking(false);
      focusAfter.current = "td-variants";
    } catch (e) {
      setError(e);
    }
  }

  return (
    <div className="page td-page">
      <BackLink fallback={{ to: "/problems?view=test-design", label: "Test design exercises" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">TEST DESIGN</p>
          <h1 className="page__title">{ex.title}</h1>
          <p className="page__subtitle">
            Write test cases for this specification. They run against a trusted reference and {ex.variant_count} faulty versions written for
            this exercise, and the report says which versions each case tells apart. A few well-chosen cases beat many alike.
          </p>
        </div>
      </div>

      {!ex.execution_enabled && (
        <p className="banner banner--info" role="note">Code can't run on this server. You can write and save your cases, but they won't be run here, and nothing is guessed.</p>
      )}

      <div className="td-layout">
        <Card className="stack-sm">
          <h2 className="section-title">The specification</h2>
          <p><code>{signatureText(ex)}</code></p>
          <div className="markdown"><Markdown>{ex.spec}</Markdown></div>
          <h3 className="review-minor">Examples</h3>
          <ul className="mini-list">
            {ex.examples.map((e, i) => <li key={i}><code>{formatArgs(e.input)}</code> gives <code>{formatValue(e.expected)}</code></li>)}
          </ul>
          <h3 className="review-minor">Limits</h3>
          <p className="subtle">Up to {ex.limits.max_cases} cases; arrays of up to {ex.limits.max_length} values; every number from {ex.limits.min_value} to {ex.limits.max_value}.</p>
          <p className="subtle">Related practice: <Link to="/problems?view=debugging">the debugging lab</Link> and <Link to="/problems?view=code-review">code review</Link>. Nothing here changes your plan.</p>
        </Card>

        <section className="stack-sm" aria-labelledby="td-cases-title">
          <h2 className="section-title" id="td-cases-title">Your cases</h2>
          <ol className="stack-sm td-editor">
            {rows.map((r, i) => {
              const p = parsed[i];
              const errs = showErrors && p && "errors" in p ? p.errors : {};
              const server = serverErrors[String(i + 1)];
              return (
                <li key={r.id} className="card stack-sm">
                  <fieldset className="stack-sm td-case">
                    <legend className="review-finding__legend">Case {i + 1}</legend>
                    {server && <p className="field__error" role="alert">{server.join(" ")}</p>}
                    <div className="td-fields">
                      {ex.params.map((param) => {
                        const id = `${r.id}-${param.name}`;
                        const err = errs[param.name];
                        return (
                          <label key={param.name} className="field" htmlFor={id}>
                            <span className="field__label"><code>{param.name}</code> ({param.type === "int[]" ? "whole numbers, comma-separated" : "whole number"})</span>
                            <input id={id} className="input" value={r.fields[param.name] ?? ""} inputMode={param.type === "int" ? "numeric" : "text"}
                              placeholder={param.type === "int[]" ? "e.g. 3, -1, 7 (empty for an empty array)" : undefined}
                              aria-invalid={err ? true : undefined} aria-describedby={err ? `${id}-error` : undefined}
                              onChange={(e) => setField(i, param.name, e.target.value)} />
                            {err && <span className="field__error" id={`${id}-error`}>{err}</span>}
                          </label>
                        );
                      })}
                      <label className="field" htmlFor={`${r.id}-expected`}>
                        <span className="field__label">Expected output</span>
                        {ex.returns === "boolean" ? (
                          <select id={`${r.id}-expected`} className="input" value={r.expected} onChange={(e) => update(i, { expected: e.target.value })}>
                            <option value="true">true</option><option value="false">false</option>
                          </select>
                        ) : (
                          <input id={`${r.id}-expected`} className="input" inputMode="numeric" value={r.expected}
                            aria-invalid={errs.expected ? true : undefined} aria-describedby={errs.expected ? `${r.id}-expected-error` : undefined}
                            onChange={(e) => update(i, { expected: e.target.value })} />
                        )}
                        {errs.expected && <span className="field__error" id={`${r.id}-expected-error`}>{errs.expected}</span>}
                      </label>
                    </div>
                    <div className="td-fields">
                      <label className="field" htmlFor={`${r.id}-label`}><span className="field__label">What kind of case (optional)</span>
                        <select id={`${r.id}-label`} className="input" value={r.label} onChange={(e) => update(i, { label: e.target.value as CaseRow["label"] })}>
                          {LABELS.map((l) => <option key={l.value} value={l.value}>{l.text}</option>)}
                        </select>
                      </label>
                      <label className="field" htmlFor={`${r.id}-note`}><span className="field__label">What it covers (optional)</span>
                        <input id={`${r.id}-note`} className="input" maxLength={500} value={r.note} onChange={(e) => update(i, { note: e.target.value })} />
                      </label>
                    </div>
                    <p><Button size="sm" variant="ghost" onClick={() => remove(i)} aria-label={`Remove case ${i + 1}`} disabled={rows.length === 1}>Remove</Button></p>
                  </fieldset>
                </li>
              );
            })}
          </ol>
          <p><Button id="td-add" variant="secondary" onClick={add} disabled={rows.length >= ex.limits.max_cases}>Add a case</Button></p>
          <div className="row">
            <Button variant="primary" loading={busy} onClick={() => void send()}>{ex.execution_enabled ? "Run my cases" : "Save my cases (not run)"}</Button>
            <span className="subtle" role="status">{status}</span>
          </div>
          <InlineError error={error} />
        </section>
      </div>

      {run.data && (
        <section className="card stack" aria-labelledby="td-result">
          <h2 className="section-title" id="td-result" tabIndex={-1}>Report</h2>
          <RunReport run={run.data} />
        </section>
      )}

      <Card className="stack-sm">
        {variants ? (
          <section className="stack-sm" aria-labelledby="td-variants">
            <h2 className="section-title" id="td-variants" tabIndex={-1}>The faulty versions</h2>
            <ul className="mini-list">{variants.map((v) => <li key={v.key}><strong>Version {v.key}: {v.title}.</strong> {v.defect}</li>)}</ul>
          </section>
        ) : asking ? (
          <div className="banner banner--info stack-sm" role="group" aria-label="Show the faulty versions?">
            <p>This shows what every faulty version gets wrong. You can still write and run your own cases afterwards.</p>
            <span className="row">
              <Button size="sm" variant="primary" onClick={() => void reveal()}>Show the faulty versions</Button>
              <Button size="sm" variant="ghost" onClick={() => setAsking(false)}>Not yet</Button>
            </span>
          </div>
        ) : (
          <p><Button size="sm" variant="ghost" onClick={() => setAsking(true)}>Stuck? Show what the faulty versions get wrong</Button></p>
        )}
      </Card>

      {runs.data && runs.data.length > 0 && (
        <section className="card stack-sm" aria-labelledby="td-earlier">
          <h2 className="section-title" id="td-earlier">Your earlier runs</h2>
          <ul className="mini-list">
            {runs.data.map((r) => (
              <li key={r.id} className="row">
                <span>{formatDateTime(r.created_at)} · {r.cases} case{r.cases === 1 ? "" : "s"} ·{" "}
                  {r.status === "done" ? `told apart ${r.caught} of ${r.total}` : r.status === "not_run" ? "not run" : r.status} · version {r.exercise_version}</span>
                <Button size="sm" variant="ghost" onClick={() => { setRunId(r.id); focusAfter.current = "td-result"; }}>Show its report</Button>
                <Button size="sm" variant="ghost" onClick={async () => {
                  const full = await api.testRun(r.id).catch(() => null);
                  if (full) { setRows(full.cases.map((c) => rowFrom(ex, c as Parameters<typeof rowFrom>[1]))); setStatus("Loaded those cases. Running them again makes a new run; the earlier one stays as it was."); }
                }}>Edit these cases</Button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="subtle">{ex.review_status} Exercise version {ex.version}.</p>
    </div>
  );
}
