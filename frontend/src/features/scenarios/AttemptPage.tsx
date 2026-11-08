import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useScenarioAttempt } from "@/api/queries";
import type { ScenarioAttempt, ScenarioStep } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { externalHref } from "@/lib/links";

const QUALITY: Record<NonNullable<ScenarioStep["quality"]>, { label: string; tone: string }> = {
  strong: { label: "Strong decision", tone: "success" },
  acceptable: { label: "Acceptable", tone: "info" },
  risky: { label: "Risky", tone: "warning" },
};

/** Playing a scenario: everything so far, the current step, and the debrief at the end. */
export function AttemptPage() {
  const { attemptId = "" } = useParams();
  const attempt = useScenarioAttempt(attemptId);
  if (attempt.isPending) return <LoadingState label="Loading your attempt…" />;
  if (attempt.isError) return <div className="page"><BackLink fallback={{ to: "/scenarios", label: "Scenarios" }} /><ErrorState error={attempt.error} onRetry={() => void attempt.refetch()} /></div>;
  return <Player attempt={attempt.data} />;
}

function Player({ attempt: a }: { attempt: ScenarioAttempt }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [choice, setChoice] = useState("");
  const [text, setText] = useState("");
  // A written response is only in this page until it's sent: leaving asks first.
  useLeaveWarning(text.trim().length > 0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const currentHeading = useRef<HTMLHeadingElement>(null);
  const debriefHeading = useRef<HTMLHeadingElement>(null);
  const moved = useRef(false);
  const cur = a.current;

  // After each step, move focus to what's new so keyboard and screen-reader users follow along.
  useEffect(() => {
    if (!moved.current) return;
    (a.debrief ? debriefHeading.current : currentHeading.current)?.focus();
  }, [a.current?.id, a.debrief]);

  async function send(body: { choice_id?: string; text?: string }) {
    if (!cur) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.scenarioStep(a.id, { node_id: cur.id, ...body });
      moved.current = true;
      qc.setQueryData(["me", "scenario-attempt", a.id], next);
      void qc.invalidateQueries({ queryKey: ["me", "scenario-attempts"] });
      setChoice("");
      setText("");
    } catch (e) {
      setError(e);
      if (e instanceof ApiError && (e.code === "stale_step" || e.code === "scenario_updated")) {
        void qc.invalidateQueries({ queryKey: ["me", "scenario-attempt", a.id] });
      }
    } finally {
      setBusy(false);
    }
  }

  async function tryAnother() {
    setBusy(true);
    try {
      const b = await api.startScenario(a.scenario.id, { mode: "exploration", parent_id: a.id });
      navigate(`/scenarios/attempts/${b.id}`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page scenario-attempt">
      <BackLink fallback={{ to: `/scenarios/${a.scenario.id}`, label: a.scenario.title }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">SCENARIO · {a.scenario.role.toUpperCase()}</p>
          <h1 className="page__title">{a.scenario.title}</h1>
          <p className="row scenario-facts">
            {a.mode === "exploration" ? <Badge tone="info">Exploration: a separate attempt; your original is kept</Badge> : <Badge>Assessed attempt</Badge>}
            <span className="subtle">Version {a.version}</span>
            {a.scenario.regulated && <Badge tone="warning">Fictional, not clinically validated</Badge>}
          </p>
        </div>
      </div>
      {a.retired && (
        <p className="banner banner--warning" role="status">
          This scenario has been updated to version {a.scenario.version}. This attempt (version {a.version}) is kept as it was{a.status === "in_progress" ? " and can't be continued" : ""}.{" "}
          <Link to={`/scenarios/${a.scenario.id}`}>Start the new version</Link>
        </p>
      )}

      <ol className="scenario-steps" aria-label="What has happened so far">
        {a.steps.map((st, i) => (
          <li key={i} id={`step-${i}`} className="card scenario-step">
            <h2 className="learn-subtitle">{st.title}</h2>
            <p>{st.text}</p>
            {st.kind === "choice" && (
              <div className="scenario-decision">
                <p><strong>You chose:</strong> {st.choice_label} {st.quality && <Badge tone={QUALITY[st.quality].tone}>{QUALITY[st.quality].label}</Badge>}</p>
                <p className="subtle"><strong>Decision rule:</strong> {st.feedback}</p>
              </div>
            )}
            {st.kind === "written" && (
              <div className="scenario-decision">
                <blockquote className="note-quote">{st.response}</blockquote>
                <p className="subtle">Covered: {st.covered?.length ? st.covered.join("; ") : "none of the points yet"}{st.missing?.length ? `. Missing: ${st.missing.join("; ")}` : ""}.</p>
              </div>
            )}
          </li>
        ))}
      </ol>

      {cur && (
        <Card className="stack-sm scenario-current" role="region" aria-labelledby="scenario-current">
          <h2 className="section-title" id="scenario-current" tabIndex={-1} ref={currentHeading}>{cur.title}</h2>
          <p>{cur.text}</p>
          {cur.kind === "info" && <span className="row"><Button variant="primary" loading={busy} onClick={() => void send({})}>Continue</Button></span>}
          {cur.kind === "choice" && (
            <form className="stack-sm" onSubmit={(e: FormEvent) => { e.preventDefault(); if (choice) void send({ choice_id: choice }); }}>
              <fieldset className="learn-question">
                <legend>Choose one</legend>
                {cur.options.map((o) => (
                  <label key={o.id} className="learn-option">
                    <input type="radio" name="scenario-choice" value={o.id} checked={choice === o.id} onChange={() => setChoice(o.id)} />
                    {o.label}
                  </label>
                ))}
              </fieldset>
              <p className="subtle" id="final-note">Your choice is final for this attempt. You can try another approach afterwards.</p>
              <span className="row"><Button type="submit" variant="primary" loading={busy} disabled={!choice} aria-describedby="final-note">Confirm this decision</Button></span>
            </form>
          )}
          {cur.kind === "written" && (
            <form className="stack-sm" onSubmit={(e: FormEvent) => { e.preventDefault(); void send({ text }); }}>
              <label className="field">
                <span className="field__label">Your response</span>
                <textarea className="input" rows={5} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} aria-describedby="written-note" />
              </label>
              <p className="subtle" id="written-note">Checked against the scenario's own points (no AI). It's final once sent.</p>
              <span className="row"><Button type="submit" variant="primary" loading={busy} disabled={text.trim().length < 10}>Send response</Button></span>
            </form>
          )}
          <InlineError error={error} />
        </Card>
      )}
      {!cur && error ? <InlineError error={error} /> : null}

      {a.debrief && (
        <section className="stack scenario-debrief" aria-labelledby="debrief-title">
          <h2 className="page__title scenario-debrief__title" id="debrief-title" tabIndex={-1} ref={debriefHeading}>Debrief</h2>
          <Card className="stack-sm">
            <p className="eyebrow">SIMULATED OUTCOME</p>
            <p className="scenario-outcome">{a.debrief.outcome}</p>
            <p>{a.debrief.summary}</p>
            <p className="subtle">{a.debrief.disclaimer}</p>
          </Card>
          <Card className="stack-sm">
            <h3 className="section-title">Your path</h3>
            <ol className="learn-walkthrough">{a.debrief.path.map((p, i) => <li key={i}>{p}</li>)}</ol>
          </Card>
          <Card className="stack-sm">
            <h3 className="section-title">Key decisions</h3>
            {a.debrief.decisions.map((d) => (
              <div key={d.step_index} className="stack-sm scenario-decision">
                <p><a href={`#step-${d.step_index}`}>{d.title}</a>: <strong>{d.chosen}</strong> <Badge tone={QUALITY[d.quality].tone}>{QUALITY[d.quality].label}</Badge></p>
                <p className="subtle">Decision rule: {d.rule}</p>
                {d.alternatives.length > 0 && (
                  <details>
                    <summary>Other approaches</summary>
                    <ul className="mini-list">{d.alternatives.map((alt) => <li key={alt.label}><strong>{alt.label}</strong> ({QUALITY[alt.quality].label.toLowerCase()}): {alt.rule}</li>)}</ul>
                  </details>
                )}
              </div>
            ))}
          </Card>
          {a.debrief.strengths.length > 0 && (
            <Card className="stack-sm">
              <h3 className="section-title">Strengths in this attempt</h3>
              <ul className="mini-list">{a.debrief.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
            </Card>
          )}
          {a.debrief.written.length > 0 && (
            <Card className="stack-sm">
              <h3 className="section-title">Your written responses</h3>
              {a.debrief.written.map((w) => (
                <p key={w.step_index}><a href={`#step-${w.step_index}`}>{w.title}</a>: covered {w.covered.length} of {w.covered.length + w.missing.length} points{w.missing.length ? ` (missing: ${w.missing.join("; ").toLowerCase()})` : ""}.</p>
              ))}
            </Card>
          )}
          <Card className="stack-sm">
            <h3 className="section-title">References</h3>
            <ul className="learn-refs">
              {a.debrief.references.map((r) => (
                <li key={r.title}>{externalHref(r.url) ? <a href={externalHref(r.url)} target="_blank" rel="noopener noreferrer">{r.title}</a> : <span>{r.title}</span>}<span className="subtle"> · {r.publisher}</span>{r.note && <span className="subtle learn-refs__note">{r.note}</span>}</li>
              ))}
            </ul>
            <p className="subtle">{a.debrief.feedback_source}</p>
          </Card>
          <span className="row">
            <Button variant="primary" loading={busy} onClick={() => void tryAnother()}>Try another approach</Button>
            <Link className="btn btn--secondary btn--md" to={`/scenarios/${a.scenario.id}`}>Back to the scenario</Link>
          </span>
        </section>
      )}
    </div>
  );
}
