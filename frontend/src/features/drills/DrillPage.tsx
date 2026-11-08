import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useDrill, useDrillAttempts } from "@/api/queries";
import type { DrillAttempt } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { SaveControls } from "@/features/saved/SaveControls";
import { ScheduleLink } from "@/features/schedule/ScheduleLink";
import { useDictation } from "@/features/voice/useDictation";
import { useStoredDraft } from "@/hooks/useStoredDraft";
import { formatDateTime } from "@/lib/format";

/** One drill: the objective and what feedback looks for up front, then a spoken or typed answer. */
export function DrillPage() {
  const { id = "" } = useParams();
  const { user } = useAuth();
  const qc = useQueryClient();
  const drill = useDrill(id);
  const attempts = useDrillAttempts(id);
  const [text, setText, kept] = useStoredDraft(`drill-draft:${user?.id ?? "anon"}:${id}`);
  const textRef = useRef(text);
  useLayoutEffect(() => {
    textRef.current = text; // dictated words are appended to what's in the box right now
  });
  const [usedVoice, setUsedVoice] = useState(false);
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [params, setParams] = useSearchParams();
  const [fresh, setFresh] = useState<DrillAttempt | null>(null);
  const [delivery, setDelivery] = useState(() => {
    try { return localStorage.getItem("codecoach.drills.delivery") !== "off"; } catch { return true; }
  });
  // Spoken time is measured only while the microphone is actually listening.
  const spokenMs = useRef(0);
  const listeningSince = useRef<number | null>(null);
  const dictation = useDictation((said) => {
    setUsedVoice(true);
    const current = textRef.current;
    setText((current && !/\s$/.test(current) ? `${current} ` : current) + said);
  });
  useEffect(() => {
    if (dictation.state === "listening") listeningSince.current = Date.now();
    else if (listeningSince.current !== null) {
      spokenMs.current += Date.now() - listeningSince.current;
      listeningSince.current = null;
    }
  }, [dictation.state]);

  const shownId = params.get("attempt");
  // A linked attempt (from your history) opens from the URL, so Back and reloads keep it.
  const result = (shownId && attempts.data?.find((a) => a.id === shownId)) || fresh;
  const show = (a: DrillAttempt) => { setFresh(a); setParams({ attempt: a.id }, { replace: false }); };
  const toggleDelivery = (on: boolean) => {
    setDelivery(on);
    try { localStorage.setItem("codecoach.drills.delivery", on ? "on" : "off"); } catch { /* blocked: this visit only */ }
  };

  if (drill.isPending) return <LoadingState label="Loading the drill…" />;
  if (drill.isError) return <div className="page"><ErrorState error={drill.error} onRetry={() => void drill.refetch()} /></div>;
  const d = drill.data;
  const listening = dictation.state === "listening";
  const words = (text.match(/[A-Za-z0-9']+/g) ?? []).length;

  async function send() {
    setBusy(true);
    setError(null);
    const sent = text;
    try {
      const seconds = Math.round(spokenMs.current / 1000);
      const out = await api.submitDrill(d.id, {
        text: sent, source: usedVoice ? "voice" : "typed", spoken_seconds: delivery && usedVoice && seconds > 0 ? seconds : null, client_request_id: requestId,
      });
      show(out);
      // Clear only what was sent: words typed or dictated while it was sending stay in the box.
      if (textRef.current === sent) setText("");
      setUsedVoice(false);
      spokenMs.current = 0;
      setRequestId(crypto.randomUUID());
      void qc.invalidateQueries({ queryKey: ["me", "drills"] });
    } catch (e) {
      setError(e); // the words stay in the box (and on this device)
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page drill-page">
      <BackLink fallback={{ to: "/drills", label: "All drills" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">DRILL</p>
          <h1 className="page__title">{d.title}</h1>
          <p className="page__subtitle">{d.objective}</p>
        </div>
      </div>
      <div className="drill-page__layout">
        <div className="stack">
          <Card className="stack-sm">
            <h2 className="section-title">Your prompt</h2>
            <p className="drill-prompt">{d.prompt}</p>
            <h3 className="section-title">Helpful feedback looks for</h3>
            <ul className="mini-list">{d.looks_for.map((l) => <li key={l}>{l}</li>)}</ul>
            {d.target_seconds && delivery ? <p className="subtle">Aim for about {d.target_seconds} seconds. It's a guide, not a score.</p> : <p className="subtle">There's no time limit, and speed isn't scored.</p>}
            <label className="checkbox"><input type="checkbox" checked={delivery} onChange={(e) => toggleDelivery(e.target.checked)} />Show delivery measurements (how long you spoke, and any target length)</label>
          </Card>

          <section className="card stack-sm" aria-labelledby="drill-answer">
            <h2 className="section-title" id="drill-answer">Your answer</h2>
            {dictation.supported ? (
              <div className="row">
                {listening
                  ? <Button variant="secondary" onClick={dictation.stop}>Stop speaking</Button>
                  : <Button variant="secondary" onClick={dictation.start} disabled={busy}>Speak your answer</Button>}
                <span className="subtle" role="status">{listening ? "Listening… what you say appears below, and you can edit it before sending." : dictation.state === "denied" ? "" : "Or type below."}</span>
              </div>
            ) : <p className="subtle">Speaking needs speech recognition, which this browser doesn't offer. Typing works the same.</p>}
            {dictation.error && <p className="banner banner--warning" role="alert">{dictation.error}</p>}
            {dictation.interim && <p className="subtle drill-interim" aria-hidden="true">{dictation.interim}</p>}
            <label className="field"><span className="field__label">Answer (check and edit before sending)</span>
              <textarea className="input" rows={6} maxLength={4000} value={text} onChange={(e) => setText(e.target.value)} />
            </label>
            <span className="subtle">{words} {words === 1 ? "word" : "words"}{text.trim() ? (kept ? " · kept on this device until you send it" : " · this browser can't keep a copy") : ""}</span>
            <InlineError error={error} />
            <span className="row">
              <Button variant="primary" loading={busy} disabled={words < 3 || listening} onClick={() => void send()}>Get feedback</Button>
              <ScheduleLink kind="drill" refId={d.id} title={d.title} label="Add this drill to my schedule" />
            </span>
          </section>

          {result && <Feedback a={result} delivery={delivery} />}
          <SaveControls item={{ item_type: "drill", track: "", ref_id: d.id }} title={d.title} />
        </div>
        <aside className="stack">
          <Card className="stack-sm">
            <h2 className="section-title">Your attempts</h2>
            {(attempts.data ?? []).length === 0 ? <p className="subtle">None yet.</p> : (
              <ol className="drill-history">
                {attempts.data!.map((a) => (
                  <li key={a.id}>
                    <button type="button" className="link-button" aria-current={result?.id === a.id ? "true" : undefined} onClick={() => show(a)}>{formatDateTime(a.created_at)}</button>
                    <span className="subtle"> · {a.source === "voice" ? "spoken" : "typed"} · {pointsThere(a)} of {(a.feedback.observations as unknown[]).length} points</span>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </aside>
      </div>
    </div>
  );
}

function pointsThere(a: DrillAttempt): number {
  return (a.feedback.observations as { present: boolean }[]).filter((o) => o.present).length;
}

function Feedback({ a, delivery }: { a: DrillAttempt; delivery: boolean }) {
  const fb = a.feedback as {
    observations: { point: string; present: boolean; detail: string }[];
    generalities: string[];
    measured: { words: number; spoken_seconds?: number; reading_estimate_seconds: number };
    notes: string[];
    limitations: string;
  };
  return (
    <section className="card stack-sm drill-feedback" aria-labelledby="drill-fb">
      <h2 className="section-title" id="drill-fb">Feedback on your attempt from {formatDateTime(a.created_at)}</h2>
      <figure className="drill-answer">
        <figcaption className="subtle">What you sent ({a.source === "voice" ? "spoken, then checked by you" : "typed"})</figcaption>
        <blockquote>{a.text}</blockquote>
      </figure>
      <ul className="drill-observations">
        {fb.observations.map((o) => (
          <li key={o.point}><Badge tone={o.present ? "success" : "neutral"}>{o.present ? "There" : "Not found"}</Badge> {o.point} <span className="subtle">({o.detail})</span></li>
        ))}
      </ul>
      {fb.generalities.length > 0 && <p>Broad claims with nothing concrete beside them: {fb.generalities.map((g) => `“${g}”`).join(", ")}. An example would back them up.</p>}
      <h3 className="section-title">Measured</h3>
      <ul className="mini-list">
        <li>{fb.measured.words} words</li>
        {!delivery ? null : fb.measured.spoken_seconds !== undefined
          ? <li>You spoke for {fb.measured.spoken_seconds} seconds (timed while the microphone was on)</li>
          : <li>Spoken time: not measured{a.source === "typed" ? " (typed answer)" : ""}</li>}
        <li>About {fb.measured.reading_estimate_seconds} seconds to say aloud at an average pace (an estimate, not a measurement)</li>
      </ul>
      {fb.notes.filter((n) => delivery || !n.startsWith("The aim is about")).map((n) => <p key={n} className="subtle">{n}</p>)}
      {a.compared_with_previous && (
        <>
          <h3 className="section-title">Compared with your previous attempt</h3>
          <ul className="mini-list">{a.compared_with_previous.map((c) => <li key={c}>{c}</li>)}</ul>
        </>
      )}
      <p className="subtle">{fb.limitations}</p>
    </section>
  );
}
