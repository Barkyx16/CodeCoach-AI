import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useWhiteboardAttempts, useWhiteboardDraft, useWhiteboardPrompts } from "@/api/queries";
import type { WhiteboardAttempt, WhiteboardDraft, WhiteboardPrompt } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { CopyWork } from "@/components/CopyWork";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { VersionConflict } from "@/components/VersionConflict";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { recoveredSave, savedVersion } from "@/lib/conflict";
import { formatDateTime, timeAgo } from "@/lib/format";
import { useCopySince, writeCopy } from "@/lib/deviceCopies";
import { useRequestKey } from "@/lib/requestKey";

import { Canvas } from "./Canvas";
import { describe, fingerprint, fit, history, KIND_LABEL, MAX_EDGES, MAX_NODES, normalize, type Diagram, type NodeKind, type NotesKey } from "./diagram";

const NOTES: { key: NotesKey; label: string; hint: string }[] = [
  { key: "requirements", label: "Requirements", hint: "What must it do? What's out of scope?" },
  { key: "assumptions", label: "Assumptions", hint: "What are you assuming about users, traffic or data?" },
  { key: "capacity", label: "Capacity estimates", hint: "Rough numbers are enough: requests per second, storage." },
  { key: "tradeoffs", label: "Tradeoffs", hint: "What did you choose, and what does it cost or give up?" },
];

export function WhiteboardEditorPage() {
  const { promptId = "" } = useParams();
  const prompts = useWhiteboardPrompts();
  const draft = useWhiteboardDraft(promptId);
  if (prompts.isPending || draft.isPending) return <LoadingState label="Loading the whiteboard…" />;
  if (prompts.isError) return <div className="page"><ErrorState error={prompts.error} /></div>;
  if (draft.isError) return <div className="page"><ErrorState error={draft.error} onRetry={() => void draft.refetch()} /></div>;
  const prompt = prompts.data.prompts.find((p) => p.id === promptId);
  if (!prompt) return <div className="page"><ErrorState error={new ApiError(404, "not_found", "Prompt not found")} /></div>;
  return <Editor key={promptId} prompt={prompt} initial={draft.data} />;
}

function Editor({ prompt, initial }: { prompt: WhiteboardPrompt; initial: WhiteboardDraft }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const localKey = `whiteboard-draft:${user?.id ?? "anon"}:${prompt.id}`;
  const [start] = useState(() => normalize(initial.diagram));
  const since = useCopySince(localKey); // a copy removed from "Your data" after this opened isn't written back
  const [h, dispatch] = useReducer(history, { past: [], present: start, future: [] });
  const [explanation, setExplanation] = useState(initial.explanation);
  const [saved, setSaved] = useState({ diagram: start, explanation: initial.explanation, revision: initial.revision });
  const [recovery, setRecovery] = useState(() => {
    try {
      const raw = localStorage.getItem(localKey);
      const parsed = raw ? (JSON.parse(raw) as { diagram: Diagram; explanation: string; base: number }) : null;
      const kept = parsed ? { ...parsed, diagram: normalize(parsed.diagram), explanation: String(parsed.explanation ?? "") } : null;
      const same = kept && fingerprint(kept.diagram) === fingerprint(start) && kept.explanation === initial.explanation;
      return kept && !same ? kept : null;
    } catch {
      return null; // unreadable or blocked storage: nothing to offer
    }
  });
  const [selected, setSelected] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [status, setStatus] = useState("");
  // The version saved elsewhere: from a refused save (409), or newer than a kept copy being restored.
  const [against, setAgainst] = useState<WhiteboardDraft | null>(null);
  // One key per exact save: a retry after a lost reply is told "went through", not "changed elsewhere".
  const saveKey = useRequestKey();
  const [earlierSave, setEarlierSave] = useState<number | null>(null);
  const [keptHere, setKeptHere] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<"save" | "feedback" | null>(null);
  const [attempt, setAttempt] = useState<WhiteboardAttempt | null>(null);
  const [highlight, setHighlight] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);
  const attempts = useWhiteboardAttempts(prompt.id);
  const fileRef = useRef<HTMLInputElement>(null);
  const d = h.present;
  const dirty = fingerprint(d) !== fingerprint(saved.diagram) || explanation.trim() !== saved.explanation.trim();
  useLeaveWarning(dirty);
  // Unsaved work is also kept on this device, so a closed tab or a crash loses nothing.
  useEffect(() => {
    if (dirty && !recovery) {
      const ok = writeCopy(localKey, JSON.stringify({ diagram: d, explanation, base: saved.revision }), since);
      queueMicrotask(() => setKeptHere(ok)); // blocked, full or removed on purpose: the page says the copy wasn't kept
    }
  }, [d, explanation, dirty, recovery, localKey, saved.revision, since]);
  const words = (explanation.match(/\w+/g) ?? []).length;
  const base = fit(d);
  const view = { x: base.x, y: base.y, w: base.w / zoom, h: base.h / zoom };
  const lastDigestDiffers = attempt !== null && fingerprint(normalize(attempt.diagram)) !== fingerprint(d);
  const filename = `codecoach-whiteboard-${prompt.id}.json`;
  const exported = JSON.stringify(d, null, 2);

  async function save(revision = saved.revision) {
    setBusy("save");
    setError(null);
    // What's sent is what's marked saved: edits made while it's saving stay unsaved.
    const sent = { diagram: d, explanation };
    try {
      const out = await api.saveWhiteboardDraft(prompt.id,
        { ...sent, expected_revision: revision, client_request_id: saveKey.keyFor([prompt.id, revision, sent]) });
      saveKey.done();
      const recovered = recoveredSave(out);
      if (recovered?.newer) {
        // Saved (the reply was lost), then changed elsewhere: compare, don't replace this page.
        setEarlierSave(recovered.accepted);
        setAgainst(out);
        return;
      }
      setSaved({ ...sent, revision: out.revision });
      try { localStorage.removeItem(localKey); } catch { /* blocked */ }
      qc.setQueryData(["me", "whiteboard", "draft", prompt.id], out);
      setAgainst(null);
      setEarlierSave(null);
      setStatus(recovered ? `Your earlier save went through (version ${recovered.accepted}).` : "Saved to your account.");
    } catch (e) {
      if (e instanceof ApiError && e.code === "stale_revision") {
        setEarlierSave(null);
        setAgainst(savedVersion<WhiteboardDraft>(e.details) ?? (await api.whiteboardDraft(prompt.id).catch(() => null)));
      } else {
        setError(e);
      }
    } finally {
      setBusy(null);
    }
  }

  async function feedback() {
    setBusy("feedback");
    setError(null);
    try {
      const a = await api.whiteboardAttempt(prompt.id, { diagram: d, explanation });
      setAttempt(a);
      void attempts.refetch();
      setStatus("Feedback is below. The diagram you sent is kept with it; later edits don't change it.");
    } catch (e) {
      setError(e); // the diagram stays on the page and on this device
    } finally {
      setBusy(null);
    }
  }

  async function importFile(file: File) {
    setError(null);
    try {
      if (file.size > 200_000) throw new Error("That file is too large to be a whiteboard diagram (200 KB at most).");
      const parsed = JSON.parse(await file.text()) as unknown;
      // The server checks the whole format (sizes, ids, plain text only) before anything is loaded.
      const clean = await api.validateWhiteboard(parsed);
      dispatch({ type: "load", diagram: normalize(clean) });
      setStatus("Imported. Check it, then save.");
    } catch (e) {
      setError(e instanceof SyntaxError ? new Error("That file isn't valid JSON.") : e);
    }
  }

  function exportFile() {
    const url = URL.createObjectURL(new Blob([exported], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
    setStatus(`Downloaded ${filename}.`);
  }

  function takeSaved(version: WhiteboardDraft) {
    const diagram = normalize(version.diagram);
    dispatch({ type: "load", diagram });
    setExplanation(version.explanation);
    setSaved({ diagram, explanation: version.explanation, revision: version.revision });
    qc.setQueryData(["me", "whiteboard", "draft", prompt.id], version);
    setAgainst(null);
    setEarlierSave(null);
    try { localStorage.removeItem(localKey); } catch { /* blocked */ }
  }
  const inWords = (x: Diagram) => describe(x).join("\n");
  const SAVED_NOTICE = "Saved to your account.";
  // "Saved" describes the diagram at the time; after an edit the page says it's unsaved again.
  const shownStatus = status === SAVED_NOTICE && dirty ? "" : status;

  return (
    <div className="page whiteboard-page">
      <BackLink fallback={{ to: "/whiteboard", label: "Whiteboard prompts" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">WHITEBOARD · SYSTEM DESIGN</p>
          <h1 className="page__title">{prompt.title}</h1>
          <p className="page__subtitle">{prompt.objective}</p>
        </div>
      </div>
      <Card className="stack-sm wb-brief">
        <p>{prompt.brief}</p>
        <p className="subtle">A good answer addresses: {prompt.requirements.map((r) => r.text.toLowerCase()).join("; ")}.</p>
      </Card>

      {recovery && (
        <div className="banner banner--info row" role="region" aria-label="Unsaved changes">
          <span>You have unsaved changes to this diagram on this device.</span>
          <span className="row">
            <Button size="sm" variant="primary" onClick={() => {
              dispatch({ type: "load", diagram: recovery.diagram });
              setExplanation(recovery.explanation);
              setRecovery(null);
              // Kept against an older saved version: compare before anything is saved over it.
              if (recovery.base !== saved.revision) setAgainst({ ...initial, diagram: saved.diagram, explanation: saved.explanation, revision: saved.revision });
            }}>Restore them</Button>
            <Button size="sm" variant="ghost" onClick={() => { try { localStorage.removeItem(localKey); } catch { /* blocked */ } setRecovery(null); }}>Discard them</Button>
          </span>
        </div>
      )}

      <div className="wb-layout">
        <section className="stack-sm" aria-labelledby="wb-canvas-title">
          <div className="wb-toolbar">
            <h2 className="section-title" id="wb-canvas-title">Diagram</h2>
            <span className="row">
              <Button size="sm" variant="ghost" disabled={!h.past.length} onClick={() => dispatch({ type: "undo" })}>Undo</Button>
              <Button size="sm" variant="ghost" disabled={!h.future.length} onClick={() => dispatch({ type: "redo" })}>Redo</Button>
              <Button size="sm" variant="ghost" onClick={() => setZoom((z) => Math.min(3, z * 1.25))}>Zoom in</Button>
              <Button size="sm" variant="ghost" onClick={() => setZoom((z) => Math.max(0.4, z / 1.25))}>Zoom out</Button>
              <Button size="sm" variant="ghost" onClick={() => setZoom(1)}>Fit to content</Button>
              <span className="subtle" aria-live="polite">Zoom {Math.round(zoom * 100)}%</span>
            </span>
          </div>
          <div className="wb-canvas-wrap">
            <Canvas diagram={d} view={view} selected={selected} highlighted={highlight} onSelect={setSelected}
              onDrop={(id, x, y) => dispatch({ type: "placeNode", id, x, y })} />
          </div>
          <details className="wb-summary">
            <summary>The diagram in words</summary>
            {d.nodes.length === 0 ? <p className="subtle">Empty so far.</p> : <ul className="mini-list">{describe(d).map((line) => <li key={line}>{line}</li>)}</ul>}
          </details>
        </section>

        <Outline d={d} dispatch={dispatch} selected={selected} onSelect={setSelected} />
      </div>

      <Card className="stack-sm">
        <h2 className="section-title">Your reasoning</h2>
        {NOTES.map((n) => (
          <label key={n.key} className="field"><span className="field__label">{n.label}</span>
            <span className="subtle">{n.hint}</span>
            <textarea className="input" rows={2} maxLength={2000} value={d.notes[n.key]} onChange={(e) => dispatch({ type: "notes", key: n.key, value: e.target.value })} />
          </label>
        ))}
        <label className="field"><span className="field__label">Explain one decision before you ask for feedback</span>
          <span className="subtle">In your own words: what you chose and why. At least 15 words ({words} so far). You can also answer in words only, with no diagram.</span>
          <textarea className="input" rows={3} maxLength={4000} value={explanation} onChange={(e) => setExplanation(e.target.value)} />
        </label>
      </Card>

      <div className="wb-actions">
        <Button variant="secondary" loading={busy === "save"} disabled={!dirty} onClick={() => void save()}>Save draft</Button>
        <Button variant="primary" loading={busy === "feedback"} disabled={words < 15} onClick={() => void feedback()}>Get feedback</Button>
        <Button variant="ghost" aria-expanded={exporting} onClick={() => setExporting((x) => !x)}>Export JSON…</Button>
        <Button variant="ghost" onClick={() => fileRef.current?.click()}>Import JSON…</Button>
        <input ref={fileRef} type="file" accept="application/json,.json" className="visually-hidden" aria-label="Import a diagram file" tabIndex={-1}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void importFile(f); e.target.value = ""; }} />
        <span className="subtle" role="status">{shownStatus || (dirty ? (keptHere ? "Unsaved changes, kept on this device" : "Unsaved changes, and this browser can't keep a copy: save, or copy your work") : saved.revision ? "Saved to your account" : "")}</span>
        {dirty && !keptHere && <CopyWork text={`${inWords(d)}\n\n${explanation}`} label="Copy your work" />}
      </div>
      {exporting && (
        <Card className="stack-sm wb-export">
          <h2 className="section-title">Export preview</h2>
          <p className="subtle">The file <strong>{filename}</strong> holds exactly this: components, connections and notes as plain text. Your explanation and feedback aren't included. Image and PDF export aren't offered.</p>
          <pre tabIndex={0} aria-label="What the file will contain">{exported}</pre>
          <span className="row"><Button size="sm" variant="primary" onClick={exportFile}>Download {filename}</Button><Button size="sm" variant="ghost" onClick={() => setExporting(false)}>Close</Button></span>
        </Card>
      )}
      {against && (
        <VersionConflict what="diagram" earlierSave={earlierSave} savedWhen={`version ${against.revision}${against.updated_at ? `, ${timeAgo(against.updated_at)}` : ""}`}
          busy={busy === "save"} keepMineLabel="Keep mine as the newest"
          fields={[
            { label: "The diagram in words", mine: inWords(d), saved: inWords(normalize(against.diagram)) },
            { label: "Your explanation", mine: explanation, saved: against.explanation },
          ]}
          onKeepMine={() => void save(against.revision)}
          onUseSaved={() => takeSaved(against)} />
      )}
      <InlineError error={error} />

      {attempt && <Feedback attempt={attempt} changed={lastDigestDiffers} onRefs={(refs) => setHighlight(new Set(refs))} />}
      {attempts.data && attempts.data.length > 0 && (
        <Card className="stack-sm">
          <h2 className="section-title">Your attempts</h2>
          <ul className="mini-list">
            {attempts.data.map((a) => (
              <li key={a.id}>
                <button type="button" className="link-button" onClick={async () => setAttempt(await api.whiteboardAttemptById(a.id))}>{formatDateTime(a.created_at)}</button>
                <span className="subtle"> · {a.addressed} of {a.total} points addressed · prompt v{a.prompt_version}, rubric v{a.rubric_version}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <p className="subtle">Limits: up to {MAX_NODES} components and {MAX_EDGES} connections, plain text only.</p>
    </div>
  );
}

function Outline({ d, dispatch, selected, onSelect }: {
  d: Diagram; dispatch: (a: Parameters<typeof history>[1]) => void; selected: string | null; onSelect: (id: string | null) => void;
}) {
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState<NodeKind>("service");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [edgeLabel, setEdgeLabel] = useState("");
  const name = (id: string) => d.nodes.find((n) => n.id === id)?.label || id;
  return (
    <section className="stack-sm wb-outline" aria-labelledby="wb-outline-title">
      <h2 className="section-title" id="wb-outline-title">Outline</h2>
      <p className="subtle">Everything on the canvas can be done here with a keyboard.</p>
      <form className="row" onSubmit={(e) => { e.preventDefault(); if (label.trim()) { dispatch({ type: "addNode", label: label.trim(), kind }); setLabel(""); } }}>
        <label className="field"><span className="field__label">New component</span><input className="input" maxLength={60} value={label} onChange={(e) => setLabel(e.target.value)} /></label>
        <label className="field"><span className="field__label">Kind</span>
          <select className="select" value={kind} onChange={(e) => setKind(e.target.value as NodeKind)}>
            {(Object.keys(KIND_LABEL) as NodeKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
          </select>
        </label>
        <Button type="submit" size="sm" disabled={!label.trim() || d.nodes.length >= MAX_NODES}>Add component</Button>
      </form>
      <h3 className="section-title">Components</h3>
      <ul className="wb-list">
        {d.nodes.map((n) => (
          <li key={n.id} className={selected === n.id ? "wb-list__selected" : undefined}>
            <label className="field"><span className="field__label">Name of {n.id}</span>
              <input className="input" maxLength={60} value={n.label} onFocus={() => onSelect(n.id)} onChange={(e) => dispatch({ type: "updateNode", id: n.id, patch: { label: e.target.value } })} />
            </label>
            <label className="field"><span className="field__label">Kind of {n.id}</span>
              <select className="select" value={n.kind} onChange={(e) => dispatch({ type: "updateNode", id: n.id, patch: { kind: e.target.value as NodeKind } })}>
                {(Object.keys(KIND_LABEL) as NodeKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
              </select>
            </label>
            <label className="field"><span className="field__label">Group of {n.id} (optional)</span>
              <input className="input" maxLength={40} value={n.group ?? ""} onChange={(e) => dispatch({ type: "updateNode", id: n.id, patch: { group: e.target.value || null } })} />
            </label>
            <span className="row wb-move" role="group" aria-label={`Move ${n.label || n.id}`}>
              <Button size="sm" variant="ghost" onClick={() => dispatch({ type: "moveNode", id: n.id, dx: -40, dy: 0 })}>Left</Button>
              <Button size="sm" variant="ghost" onClick={() => dispatch({ type: "moveNode", id: n.id, dx: 40, dy: 0 })}>Right</Button>
              <Button size="sm" variant="ghost" onClick={() => dispatch({ type: "moveNode", id: n.id, dx: 0, dy: -40 })}>Up</Button>
              <Button size="sm" variant="ghost" onClick={() => dispatch({ type: "moveNode", id: n.id, dx: 0, dy: 40 })}>Down</Button>
              <Button size="sm" variant="ghost" aria-label={`Delete ${n.label || n.id}`} onClick={() => dispatch({ type: "deleteNode", id: n.id })}>Delete</Button>
            </span>
          </li>
        ))}
      </ul>
      <h3 className="section-title">Connections</h3>
      <ul className="wb-list">
        {d.edges.map((e) => (
          <li key={e.id}>
            <span>{name(e.source)} → {name(e.target)} <Badge>{e.id}</Badge></span>
            <label className="field"><span className="field__label">Label of {e.id}</span>
              <input className="input" maxLength={60} value={e.label} onChange={(ev) => dispatch({ type: "updateEdge", id: e.id, label: ev.target.value })} />
            </label>
            <Button size="sm" variant="ghost" aria-label={`Delete connection ${e.id}`} onClick={() => dispatch({ type: "deleteEdge", id: e.id })}>Delete</Button>
          </li>
        ))}
      </ul>
      <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); dispatch({ type: "addEdge", source: from, target: to, label: edgeLabel.trim() }); setEdgeLabel(""); }}>
        <div className="app-form__grid">
          <label className="field"><span className="field__label">From</span>
            <select className="select" value={from} onChange={(e) => setFrom(e.target.value)}><option value="">Choose…</option>{d.nodes.map((n) => <option key={n.id} value={n.id}>{n.label || n.id}</option>)}</select>
          </label>
          <label className="field"><span className="field__label">To</span>
            <select className="select" value={to} onChange={(e) => setTo(e.target.value)}><option value="">Choose…</option>{d.nodes.map((n) => <option key={n.id} value={n.id}>{n.label || n.id}</option>)}</select>
          </label>
          <label className="field"><span className="field__label">What flows</span><input className="input" maxLength={60} value={edgeLabel} onChange={(e) => setEdgeLabel(e.target.value)} /></label>
        </div>
        <span><Button type="submit" size="sm" disabled={!from || !to || from === to || d.edges.length >= MAX_EDGES}>Add connection</Button></span>
      </form>
    </section>
  );
}

function Feedback({ attempt, changed, onRefs }: { attempt: WhiteboardAttempt; changed: boolean; onRefs: (refs: string[]) => void }) {
  const fb = attempt.feedback as {
    checks: { ok: boolean; message: string; refs: string[] }[];
    rubric: { requirement: string; text: string; addressed: boolean; evidence: { kind: string; id: string; text: string }[] }[];
    reasoning: { ok: boolean; message: string; refs: string[] }[];
    limitations: string[];
  };
  return (
    <section className="card stack-sm wb-feedback" aria-labelledby="wb-fb-title">
      <h2 className="section-title" id="wb-fb-title">Feedback on the attempt from {formatDateTime(attempt.created_at)}</h2>
      {changed && <p className="banner banner--info">Your diagram has changed since this attempt. This feedback is about the version you sent.</p>}
      <h3 className="section-title">Checks of the diagram itself</h3>
      <ul className="mini-list">{fb.checks.map((c) => (
        <li key={c.message}>{c.ok ? "✓" : "•"} {c.message}{c.refs.length > 0 && <> <button type="button" className="link-button" onClick={() => onRefs(c.refs)}>Show on the diagram</button></>}</li>
      ))}</ul>
      <h3 className="section-title">What your design addresses</h3>
      <ul className="wb-rubric">
        {fb.rubric.map((r) => (
          <li key={r.requirement}>
            <Badge tone={r.addressed ? "success" : "neutral"}>{r.addressed ? "Addressed" : "Not found"}</Badge> {r.text}
            {r.evidence.length > 0 && (
              <p className="subtle">Found in: {r.evidence.map((e) => `${e.kind} ${e.id}`).join(", ")} <button type="button" className="link-button" onClick={() => onRefs(r.evidence.map((e) => e.id))}>Show on the diagram</button></p>
            )}
          </li>
        ))}
      </ul>
      <h3 className="section-title">Your reasoning</h3>
      <ul className="mini-list">{fb.reasoning.map((r) => <li key={r.message}>{r.ok ? "✓" : "•"} {r.message}</li>)}</ul>
      <ul className="mini-list subtle">{fb.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
      <p className="subtle">Prompt version {attempt.prompt_version}, rubric version {attempt.rubric_version}.</p>
    </section>
  );
}
