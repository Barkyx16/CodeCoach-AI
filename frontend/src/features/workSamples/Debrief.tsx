import { useState } from "react";

import type { WorkSampleAttempt, WorkSampleFeedback } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";

/**
 * The checks' feedback on one attempt, every note tied to the learner's own sentence or to the
 * brief: required parts, the points covered (quoted) and missing (with the brief's guidance),
 * details and claims the facts don't support, words wrong for the audience, long sentences, and one
 * revision to try. One good approach appears only when asked, and only as one approach.
 */
export function Debrief({ attempt }: { attempt: WorkSampleAttempt }) {
  const fb = attempt.feedback as unknown as WorkSampleFeedback;
  const [showReference, setShowReference] = useState(false);
  const covered = fb.points.filter((p) => p.covered);
  const missing = fb.points.filter((p) => !p.covered);
  const notInBrief = [...fb.claims.map((c) => ({ key: `c-${c.phrase}`, text: c.phrase, sentence: c.sentence, why: c.why })),
    ...fb.unsupported.map((u) => ({ key: `u-${u.text}`, text: u.text, sentence: u.sentence, why: u.why }))];
  return (
    <div className="stack ws-debrief">
      <section className="card stack-sm" aria-label="Required parts">
        <h3 className="section-title">Required parts</h3>
        <ul className="mini-list">
          {fb.checks.map((c) => <li key={c.id}><Badge tone={c.ok ? "success" : "warning"}>{c.ok ? "OK" : "Check"}</Badge> {c.text}</li>)}
        </ul>
        <p>Covers {fb.covered} of the {fb.total} points the brief asks for.</p>
      </section>
      {covered.length > 0 && (
        <section className="card stack-sm" aria-label="What you covered">
          <h3 className="section-title">What you covered</h3>
          <ul className="stack-sm ws-points">
            {covered.map((p) => (
              <li key={p.id}><strong>{p.label}</strong>{p.quote && <>: <q className="ws-quote">{p.quote}</q></>}</li>
            ))}
          </ul>
        </section>
      )}
      {missing.length > 0 && (
        <section className="card stack-sm" aria-label="Missing">
          <h3 className="section-title">Missing</h3>
          <ul className="stack-sm ws-points">{missing.map((p) => <li key={p.id}><strong>{p.label}.</strong> {p.guidance}</li>)}</ul>
        </section>
      )}
      {notInBrief.length > 0 && (
        <section className="card stack-sm ws-flags" aria-label="Not supported by the brief">
          <h3 className="section-title">Not supported by the brief</h3>
          <ul className="stack-sm ws-points">
            {notInBrief.map((n) => <li key={n.key}><strong>“{n.text}”</strong> in <q className="ws-quote">{n.sentence}</q>. {n.why}</li>)}
          </ul>
        </section>
      )}
      {(fb.jargon.length > 0 || fb.long_sentences.length > 0) && (
        <section className="card stack-sm" aria-label="Audience and clarity">
          <h3 className="section-title">Audience and clarity</h3>
          <ul className="stack-sm ws-points">
            {fb.jargon.map((j) => <li key={j.term}><strong>“{j.term}”</strong>: {j.why}</li>)}
            {fb.long_sentences.map((l) => <li key={l.sentence}>A {l.words}-word sentence: <q className="ws-quote">{l.sentence}</q></li>)}
          </ul>
        </section>
      )}
      <section className="card stack-sm" aria-label="One revision to try">
        <h3 className="section-title">One revision to try</h3>
        <p>{fb.revision}</p>
      </section>
      <p className="subtle">{fb.method} This is practice evidence, not a credential or proof of how you'd perform at work.</p>
      {showReference ? (
        <section className="card stack-sm" aria-label="One good approach">
          <h3 className="section-title">One good approach</h3>
          <p className="subtle">One way to do it. Your wording, order and style don't need to match: what matters is covering the points with the facts.</p>
          {Object.entries(attempt.reference).map(([sid, text]) => (
            <div key={sid} className="stack-sm">
              {sid !== "message" && <h4 className="review-minor">{attempt.section_labels[sid] ?? sid}</h4>}
              <p className="ws-text">{text}</p>
            </div>
          ))}
        </section>
      ) : (
        <p><Button size="sm" variant="ghost" onClick={() => setShowReference(true)}>Show one good approach</Button></p>
      )}
    </div>
  );
}
