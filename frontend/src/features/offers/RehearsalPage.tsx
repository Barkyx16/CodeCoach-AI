import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useOfferRehearsal } from "@/api/queries";
import type { AnswerSource, OfferDebrief, OfferRehearsal } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { PrivateUnavailable } from "@/components/Unavailable";
import { useStoredDraft } from "@/hooks/useStoredDraft";
import { isGone } from "@/lib/errors";
import { useRequestKey } from "@/lib/requestKey";
import { useInterviewerVoice } from "@/features/voice/useInterviewerVoice";
import { VoiceComposer } from "@/features/voice/VoiceComposer";
import { useVoicePrefs } from "@/features/voice/voicePrefs";

import { FactCard } from "./FactCard";

/**
 * A live offer rehearsal (Volume 10, prompt 8; docs/OFFER_REHEARSAL.md): the fictional card, the
 * conversation so far, and the answer box every interview uses (typed, or dictated with the
 * microphone on only after a click). The server keeps the conversation; a resent turn is
 * recognised, and a turn written against an older state is refused rather than talking over
 * another tab. Stop is always there, and nothing is sent to anyone.
 */
export function RehearsalPage() {
  const { rehearsalId = "" } = useParams();
  const r = useOfferRehearsal(rehearsalId);
  if (r.isPending) return <LoadingState label="Loading your rehearsal…" />;
  if (r.isError && isGone(r.error)) return <PrivateUnavailable what="rehearsal" list={{ to: "/offers", label: "Offer conversations" }} />;
  if (r.isError) return <div className="page"><ErrorState error={r.error} onRetry={() => void r.refetch()} /></div>;
  return <Rehearsal r={r.data} />;
}

function Rehearsal({ r }: { r: OfferRehearsal }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [prefs] = useVoicePrefs();
  const voice = useInterviewerVoice(prefs);
  const [draft, setDraft] = useStoredDraft(`offer-rehearsal-draft:${user?.id ?? "anon"}:${r.id}:${r.phase}`);
  const keys = useRequestKey();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const live = r.status === "in_progress";
  const latest = useRef<HTMLHeadingElement>(null);
  const debriefHeading = useRef<HTMLHeadingElement>(null);
  const moved = useRef(false);
  const phaseIndex = r.card.phases.findIndex((p) => p.id === r.phase);
  const next = r.card.phases[phaseIndex + 1];

  useEffect(() => {
    if (!moved.current) return;
    (r.status === "completed" ? debriefHeading.current : latest.current)?.focus();
  }, [r.turns.length, r.status]);

  const keep = (next: OfferRehearsal) => {
    moved.current = true;
    qc.setQueryData(["me", "offer-rehearsal", r.id], next);
    void qc.invalidateQueries({ queryKey: ["me", "offer-rehearsals"] });
  };
  async function act<T>(fn: () => Promise<T>): Promise<T | null> {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e);
      if (e instanceof ApiError && (e.code === "rehearsal_advanced" || e.code === "rehearsal_finished")) {
        void qc.invalidateQueries({ queryKey: ["me", "offer-rehearsal", r.id] });
      }
      return null;
    } finally {
      setBusy(false);
    }
  }
  async function send(source: AnswerSource): Promise<boolean> {
    const text = draft.trim();
    if (!text) return false;
    const after = r.turns[r.turns.length - 1]?.seq ?? 0;
    const key = keys.keyFor({ id: r.id, after, text });
    const got = await act(() => api.offerTurn(r.id, { text, source, after_seq: after, client_request_id: key }));
    if (!got) return false;
    keys.done();
    setDraft("");
    keep(got);
    return true;
  }
  const advance = async () => { const got = await act(() => api.offerAdvance(r.id, r.phase)); if (got) keep(got); };
  const finish = async () => { const got = await act(() => api.offerFinish(r.id)); if (got) keep(got); };
  const again = async () => {
    const got = await act(() => api.startOfferRehearsal({ case_id: r.case_id, goals: r.goals, parent_id: r.id }));
    if (got) navigate(`/offers/rehearsals/${got.id}`);
  };

  const lastCounterpart = [...r.turns].reverse().find((t) => t.speaker === "counterpart");
  return (
    <div className="page offers-rehearsal">
      <BackLink fallback={{ to: "/offers", label: "Offer conversations" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">OFFER CONVERSATION · FICTIONAL</p>
          <h1 className="page__title">{r.card.title}</h1>
          <p className="row offer-facts">
            <Badge tone="info">{r.mode}</Badge>
            {r.parent_id && <Badge>A different approach: your earlier rehearsal is kept</Badge>}
            {r.current_version !== r.case_version && <span className="subtle">This card was edited since; this rehearsal keeps version {r.case_version}.</span>}
          </p>
        </div>
      </div>
      <div className="offers-layout">
        <aside className="stack offers-side">
          <FactCard card={r.card} />
          {r.goals.length > 0 && (
            <section className="card stack-sm" aria-labelledby="offer-my-goals">
              <h2 className="section-title" id="offer-my-goals">Your goals (you wrote these)</h2>
              <ul className="mini-list">{r.goals.map((g) => <li key={g} className="offer-text">{g}</li>)}</ul>
            </section>
          )}
        </aside>
        <div className="stack offers-main">
          <ol className="offer-phases" aria-label="Parts of the conversation">
            {r.card.phases.map((p, i) => (
              <li key={p.id} className={i === phaseIndex ? "is-current" : i < phaseIndex ? "is-done" : ""} aria-current={i === phaseIndex && live ? "step" : undefined}>
                {i + 1}. {p.title}{i < phaseIndex ? " (done)" : i === phaseIndex && live ? " (now)" : ""}
              </li>
            ))}
          </ol>
          <section className="card stack-sm" aria-labelledby="offer-transcript">
            <h2 className="section-title" id="offer-transcript">The conversation</h2>
            <ol className="offer-transcript" aria-label="Transcript">
              {r.turns.map((t) => (
                <li key={t.seq} className={`offer-turn offer-turn--${t.speaker}`}>
                  <span className="offer-turn__who">{t.speaker === "learner" ? `You${t.source === "voice" ? " (spoken)" : ""}` : `${r.card.counterpart.split(",")[0]} (scripted)`}</span>
                  <p className="offer-text">{t.text}</p>
                </li>
              ))}
            </ol>
            <h3 className="visually-hidden" tabIndex={-1} ref={latest}>Latest reply</h3>
            {live && voice.supported && lastCounterpart && (
              <span className="row">
                {voice.speaking
                  ? <Button size="sm" variant="ghost" onClick={voice.stop}>Stop reading</Button>
                  : <Button size="sm" variant="ghost" onClick={() => voice.speak(lastCounterpart.text)}>Read the reply aloud</Button>}
              </span>
            )}
          </section>
          {live && (
            <section className="stack-sm" aria-label="Your turn">
              <VoiceComposer
                key={`${r.phase}-${r.turns.length}` /* a new turn remounts it: the microphone stops */}
                id="offer-answer" label="What you'd say" value={draft} onChange={setDraft} onSubmit={send}
                submitting={busy} disabled={busy || r.turns_left_in_phase === 0} maxLength={2000} voice={voice} rows={4}
                submitLabel="Say it" placeholder="Type, or press Speak answer and talk…"
                hint={r.turns_left_in_phase > 0 ? `${r.turns_left_in_phase} turn${r.turns_left_in_phase === 1 ? "" : "s"} left in this part` : "No turns left in this part: move on or stop."}
                errorId={error ? "offer-error" : undefined}
              />
              <span className="row offer-actions">
                {next
                  ? <Button variant="secondary" loading={busy} onClick={() => void advance()}>Move on: {next.title.toLowerCase()}</Button>
                  : null}
                <Button variant="ghost" loading={busy} onClick={() => void finish()}>Stop and see the debrief</Button>
              </span>
              <p className="subtle">You can stop at any point; it's practice, and nothing is sent to anyone. Declining or asking for time are complete answers.</p>
              <InlineError id="offer-error" error={error} />
            </section>
          )}
          {!live && r.debrief && (
            <OfferDebriefView d={r.debrief as unknown as OfferDebrief} headingRef={debriefHeading} onAgain={() => void again()} busy={busy} />
          )}
          {!live && <InlineError error={error} />}
        </div>
      </div>
    </div>
  );
}

const OUTCOME: Record<NonNullable<OfferDebrief["outcome"]>, string> = {
  accept: "You accepted", decline: "You declined", time: "You asked for time", counter: "You made a counter", unclear: "No clear answer",
};

function OfferDebriefView({ d, headingRef, onAgain, busy }: { d: OfferDebrief; headingRef: React.Ref<HTMLHeadingElement>; onAgain: () => void; busy: boolean }) {
  return (
    <section className="stack offer-debrief" aria-labelledby="offer-debrief-title">
      <h2 className="page__title" id="offer-debrief-title" tabIndex={-1} ref={headingRef}>Debrief</h2>
      <section className="card stack-sm" aria-labelledby="offer-d-request">
        <h3 className="section-title" id="offer-d-request">The request you made</h3>
        {d.request ? (
          <>
            <blockquote className="note-quote offer-text">{d.request.quote}</blockquote>
            {d.request.arithmetic && (
              <p>{d.request.arithmetic.requested} against the card's {d.request.arithmetic.offered}: {d.request.arithmetic.difference}{d.request.arithmetic.per_week ? `, ${d.request.arithmetic.per_week}` : ""}.</p>
            )}
          </>
        ) : <p>No request named a term from the offer.</p>}
        {d.counteroffer.arithmetic && <p className="subtle">The scripted counteroffer: {d.counteroffer.arithmetic.from} to {d.counteroffer.arithmetic.to} ({d.counteroffer.arithmetic.difference}).</p>}
        <p className="subtle">{d.no_tax}</p>
        {d.outcome && <p><strong>{OUTCOME[d.outcome]}.</strong></p>}
      </section>
      <section className="card stack-sm" aria-labelledby="offer-d-facts">
        <h3 className="section-title" id="offer-d-facts">From the card (fictional)</h3>
        <p>Facts you used: {d.facts_used.length ? d.facts_used.map((f) => `${f.label}${f.value ? ` (${f.value})` : ""}`).join("; ") : "none of the card's terms by name"}.</p>
        <p>Still unknown: {d.unresolved.map((u) => `${u.label} (${u.asked ? "you asked; get it in writing" : "not asked about"})`).join("; ")}.</p>
        {d.goals.length > 0 && <p><strong>Your goals (you wrote these):</strong> <span className="offer-text">{d.goals.join("; ")}</span></p>}
      </section>
      {d.claims.length > 0 && (
        <section className="card stack-sm offer-claims" aria-labelledby="offer-d-claims">
          <h3 className="section-title" id="offer-d-claims">Things the card doesn't support</h3>
          <ul className="mini-list">{d.claims.map((c, i) => <li key={i}><span className="offer-text">“{c.quote}”</span>: {c.note}</li>)}</ul>
        </section>
      )}
      <section className="card stack-sm" aria-labelledby="offer-d-coaching">
        <h3 className="section-title" id="offer-d-coaching">Coaching (qualitative)</h3>
        <ul className="mini-list">
          {d.criteria.map((c) => <li key={c.id}><Badge tone={c.met ? "success" : "warning"}>{c.met ? "Done" : "Not yet"}</Badge> <strong>{c.label}:</strong> {c.note}</li>)}
        </ul>
        {d.pressure && <p className="subtle">Pressure, like an ultimatum, isn't rewarded here: the coaching looks at clarity and reasons.</p>}
        <p><strong>One thing to try next:</strong> {d.improvement}</p>
        <p className="subtle">{d.method}</p>
      </section>
      <p className="banner banner--info">{d.disclaimer}</p>
      <span className="row">
        <Button variant="primary" loading={busy} onClick={onAgain}>Try a different approach</Button>
        <Link className="btn btn--secondary btn--md" to="/offers">Back to offer conversations</Link>
      </span>
    </section>
  );
}
