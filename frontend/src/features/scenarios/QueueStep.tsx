import { useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";

import type { PlannedTask, ScenarioNode, ScenarioPlan, ScenarioStep, ScenarioTask } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { dropCopy, useCopySince, writeCopy } from "@/lib/deviceCopies";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";

/**
 * Ordering a work queue (Volume 10, prompt 7; docs/SCENARIOS.md, "Work queues"). Every task's facts
 * are on the page; Move up / Move down and a position list reorder from the keyboard, and dragging
 * is an optional extra. The order and the reasoning are kept on this device until sent. The server
 * checks the order against the case; the page never says whether an order is valid beforehand.
 */
const MIN_WORDS = 5;
const words = (t: string) => (t.match(/[\p{L}\p{N}']+/gu) ?? []).length;

interface Draft { order: string[]; text: string }

function sameTasks(order: string[], tasks: ScenarioTask[]): boolean {
  return order.length === tasks.length && [...order].sort().join("\n") === tasks.map((t) => t.id).sort().join("\n");
}

function due(t: { due?: string | null; due_is_hard?: boolean }) {
  if (!t.due) return null;
  return t.due_is_hard ? `must be done by ${t.due}` : `wanted by ${t.due}`;
}

export function QueueStep({ attemptId, node, busy, onSend }: {
  attemptId: string;
  node: ScenarioNode;
  busy: boolean;
  onSend: (body: { order: string[]; text: string }) => Promise<boolean>;
}) {
  const { user } = useAuth();
  const key = `scenario-queue-draft:${user?.id ?? "anon"}:${attemptId}:${node.id}`;
  const since = useCopySince(key); // a copy removed from "Your data" after this opened isn't written back
  const tasks = node.tasks ?? [];
  const [restored] = useState<Draft | null>(() => {
    try {
      const d = JSON.parse(localStorage.getItem(key) ?? "null") as Draft | null;
      return d && sameTasks(d.order, tasks) ? d : null;
    } catch { return null; }
  });
  const [order, setOrder] = useState<string[]>(restored?.order ?? tasks.map((t) => t.id));
  const [text, setText] = useState(restored?.text ?? "");
  const [status, setStatus] = useState(restored ? "Your order and reasoning were restored from this device." : "");
  const [timer, setTimer] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [dragging, setDragging] = useState<number | null>(null);
  const focusAfter = useRef<string | null>(null);
  const touched = useRef(Boolean(restored));
  const byId = new Map(tasks.map((t) => [t.id, t]));

  useEffect(() => {
    if (!touched.current) return;
    writeCopy(key, JSON.stringify({ order, text }), since); // blocked or removed on purpose: it lasts as long as the page
  }, [key, order, text, since]);
  useEffect(() => {
    if (!focusAfter.current) return;
    document.getElementById(focusAfter.current)?.focus();
    focusAfter.current = null;
  });
  useEffect(() => {
    if (!timer) return;
    const started = Date.now() - elapsed * 1000;
    const id = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- restart only when switched on
  }, [timer]);

  function move(from: number, to: number, via: "up" | "down" | "pos" | "drag") {
    if (to < 0 || to >= order.length || from === to) return;
    const next = [...order];
    const [id] = next.splice(from, 1);
    if (!id) return;
    next.splice(to, 0, id);
    touched.current = true;
    setOrder(next);
    setStatus(`“${byId.get(id)?.title ?? id}” is now ${to + 1} of ${next.length}.`);
    // Keep focus on the control that moved it, in the task's new place (or the other button at an end).
    const which = via === "up" && to === 0 ? "down" : via === "down" && to === next.length - 1 ? "up" : via;
    focusAfter.current = which === "drag" ? null : `queue-${which}-${id}`;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (words(text) < MIN_WORDS) { setStatus("Say what you'd do first and why, in a sentence or two."); return; }
    if (await onSend({ order, text })) {
      dropCopy(key);
    }
  }

  const onDragStart = (i: number) => (e: DragEvent) => { setDragging(i); e.dataTransfer.effectAllowed = "move"; };
  const onDrop = (i: number) => (e: DragEvent) => { e.preventDefault(); if (dragging !== null) move(dragging, i, "drag"); setDragging(null); };

  return (
    <form className="stack-sm queue" onSubmit={(e) => void submit(e)} aria-describedby="queue-how">
      <p className="subtle" id="queue-how">
        The queue starts at {node.clock}. You do one task at a time, at the case's estimates. Use Move up and Move down, or a
        task's position, to reorder; dragging works too.
      </p>
      <ol className="queue-list" aria-label="Your order">
        {order.map((id, i) => {
          const t = byId.get(id);
          if (!t) return null;
          const when = due(t);
          return (
            <li key={id} className={`card stack-sm queue-task${dragging === i ? " is-dragging" : ""}`} draggable
              onDragStart={onDragStart(i)} onDragOver={(e) => e.preventDefault()} onDrop={onDrop(i)} onDragEnd={() => setDragging(null)}>
              <div className="row queue-task__head">
                <span className="queue-task__pos" aria-hidden="true">{i + 1}</span>
                <h3 className="queue-task__title" id={`queue-title-${id}`}>{t.title}</h3>
                <span className="subtle">about {t.minutes} min</span>
                {when && <Badge tone={t.due_is_hard ? "warning" : "neutral"}>{when}</Badge>}
              </div>
              <ul className="mini-list queue-task__facts">{t.facts.map((f) => <li key={f}>{f}</li>)}</ul>
              {t.consequence && <p className="subtle"><strong>If it waits:</strong> {t.consequence}</p>}
              <span className="row queue-task__controls" role="group" aria-label={`Move “${t.title}”`}>
                <Button size="sm" variant="ghost" id={`queue-up-${id}`} disabled={i === 0} onClick={() => move(i, i - 1, "up")}
                  aria-label={`Move up: ${t.title}`}>Move up</Button>
                <Button size="sm" variant="ghost" id={`queue-down-${id}`} disabled={i === order.length - 1} onClick={() => move(i, i + 1, "down")}
                  aria-label={`Move down: ${t.title}`}>Move down</Button>
                <label className="row queue-task__position">
                  <span className="subtle">Position</span>
                  <select id={`queue-pos-${id}`} className="input queue-select" value={i} aria-label={`Position of “${t.title}”`}
                    onChange={(e) => move(i, Number(e.target.value), "pos")}>
                    {order.map((_, j) => <option key={j} value={j}>{j + 1}</option>)}
                  </select>
                </label>
              </span>
            </li>
          );
        })}
      </ol>
      <p className="visually-hidden" role="status" aria-live="polite">{status.startsWith("“") ? status : ""}</p>
      <div className="field">
        <label className="field__label" htmlFor="queue-reason">What you'd do first, and why</label>
        <span className="field__hint" id="queue-reason-hint">A sentence or two: your first actions and the reasons (who's affected, what can't wait, who you'd tell).</span>
        <textarea id="queue-reason" className="input" rows={4} maxLength={2000} value={text} aria-describedby="queue-reason-hint"
          aria-invalid={status.startsWith("Say what") && words(text) < MIN_WORDS ? true : undefined}
          onChange={(e) => { touched.current = true; setText(e.target.value); }} />
      </div>
      <div className="row queue-timer">
        <label className="row"><input type="checkbox" checked={timer} onChange={(e) => { setTimer(e.target.checked); if (!e.target.checked) setElapsed(0); }} /> Show a practice timer</label>
        {timer && <span className="subtle" aria-live="off">Practice timer: {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}</span>}
      </div>
      <p className="subtle" id="queue-timer-note">The timer is optional and just for you: it isn't saved or sent, and nothing here is judged on speed.</p>
      <p className="subtle" id="queue-final">Your order is final for this attempt. You can try another approach afterwards.</p>
      <span className="row">
        <Button type="submit" variant="primary" loading={busy} aria-describedby="queue-final">Submit this order</Button>
        <span className="subtle" role="status">{status.startsWith("“") ? "" : status}</span>
      </span>
    </form>
  );
}

function Timeline({ plan }: { plan: PlannedTask[] }) {
  return (
    <ol className="queue-timeline">
      {plan.map((p) => (
        <li key={p.id}>
          <span className="queue-timeline__time">{p.start}–{p.finish}</span> {p.title}
          {p.due && <span className={p.late ? "queue-late" : "subtle"}> ({p.late ? `after its ${p.due} time` : `by ${p.due}: on time`})</span>}
        </li>
      ))}
    </ol>
  );
}

function Constraints({ violations }: { violations: ScenarioStep["violations"] }) {
  if (!violations?.length) return <p><Badge tone="success">Possible</Badge> This order meets every hard constraint (what needs what first, and the times that can't be missed).</p>;
  return (
    <div className="banner banner--warning stack-sm">
      <p><strong>This order breaks {violations.length === 1 ? "a hard constraint" : `${violations.length} hard constraints`}:</strong></p>
      <ul className="mini-list">{violations.map((v) => <li key={v.text}>{v.kind === "dependency" ? "Needs another task first: " : "Too late: "}{v.text}</li>)}</ul>
    </div>
  );
}

/** A queue step already sent, in "What has happened so far". */
export function QueueRecord({ step }: { step: ScenarioStep }) {
  return (
    <div className="scenario-decision stack-sm">
      <p><strong>Your order</strong>, at the case's estimates:</p>
      <Timeline plan={step.plan ?? []} />
      <Constraints violations={step.violations} />
      {step.follows && step.follows.length > 0 && <p className="subtle"><strong>It follows:</strong> {step.follows.map((f) => f.label).join("; ")}.</p>}
      <blockquote className="note-quote">{step.response}</blockquote>
    </div>
  );
}

/** The debrief's account of each plan, on what the case had said by then. */
export function QueuePlans({ plans }: { plans: ScenarioPlan[] }) {
  return (
    <>
      {plans.map((p) => (
        <div key={p.step_index} className="card stack-sm queue-plan">
          <h3 className="section-title"><a href={`#step-${p.step_index}`}>{p.title}</a></h3>
          <p className="subtle">
            Judged on what you knew at {p.clock}{p.learned_before.length ? `, after: ${p.learned_before.join("; ")}` : ", before any new information"}. Later news doesn't count against it.
          </p>
          <details>
            <summary>The tasks and facts as they stood</summary>
            <ul className="mini-list">{p.known.map((t) => <li key={t.id}><strong>{t.title}</strong> (about {t.minutes} min{due(t) ? `, ${due(t)}` : ""}): {t.facts.join(" ")}</li>)}</ul>
          </details>
          <Timeline plan={p.plan} />
          <Constraints violations={p.violations} />
          {p.follows.length > 0
            ? p.follows.map((f) => <p key={f.label}><strong>Your order follows “{f.label}”.</strong> {f.explanation}</p>)
            : <p>Your order doesn't match one of the authored strategies; that's fine if it meets the hard constraints and your reasons hold.</p>}
          {p.others.length > 0 && (
            <div className="stack-sm">
              <h4 className="review-minor">Other reasonable strategies</h4>
              <ul className="mini-list">{p.others.map((o) => <li key={o.label}><strong>{o.label}:</strong> {o.explanation}</li>)}</ul>
            </div>
          )}
          <p className="subtle">More than one order can be right here: the strategies are reasonable approaches, not a ranking.</p>
          <p><strong>Your reasoning:</strong> <span className="queue-text">{p.response}</span></p>
          <p className="subtle">Tradeoffs it names (the case's own points, not AI): {p.covered.length ? p.covered.join("; ") : "none of them yet"}{p.missing.length ? `. Not mentioned: ${p.missing.join("; ")}` : ""}.</p>
        </div>
      ))}
    </>
  );
}
