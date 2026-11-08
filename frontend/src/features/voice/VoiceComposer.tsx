import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type MutableRefObject, type ReactNode } from "react";

import type { AnswerSource } from "@/api/types";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";

import { useDictation, type DictationState } from "./useDictation";
import type { InterviewerVoice } from "./useInterviewerVoice";

const STATE_TEXT: Record<DictationState, string> = {
  ready: "Ready",
  listening: "Listening. Microphone on",
  processing: "Processing your speech…",
  unavailable: "Voice input unavailable",
  denied: "Microphone blocked",
  error: "Voice input stopped",
};

/**
 * The answer box for every interview: always typeable, with optional push-to-talk dictation.
 *
 * - Explicit controls: Speak answer starts the microphone (only ever on a click), Stop listening
 *   ends it, and Discard throws away this take (everything added since Speak answer) and puts the
 *   answer back as it was. The time listened is shown, outside the announced status.
 * - Recognised (final) phrases are appended to the editable draft, each once; unconfirmed (interim)
 *   words are shown separately and never submitted. If listening fails or ends with words still
 *   unconfirmed, they're offered: add them, or leave them out.
 * - A blocked microphone can be tried again once it's allowed, without leaving the question.
 * - Submitting is disabled while the microphone is on or still processing, so partial speech is
 *   never sent; the learner stops, reviews, then submits.
 * - The microphone and the interviewer's voice never run together: talking stops playback, and
 *   playback starting cancels listening.
 * - `submitting` comes from the caller's request state. A ref also guards double submits: it
 *   holds the text being sent and is released when that send fails (so the kept draft can be
 *   sent again) or when the box shows something else (the next question, or a cleared box), so
 *   the same answer is never sent twice. It never waits for a "submitting" render, which React
 *   can skip when the answer is saved before it gets to render; waiting for one left the guard
 *   shut and the next answer's button silently did nothing.
 */
export function VoiceComposer({
  id, label, value, onChange, onSubmit, submitting, disabled = false, submitLabel, placeholder,
  voice, extraActions, maxLength, hint, rows = 8, errorId, onIgnored, submitRef,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Send the answer. Resolves true once it was saved, false if it wasn't (the draft is kept). */
  onSubmit: (source: AnswerSource) => Promise<boolean>;
  submitting: boolean;
  disabled?: boolean;
  submitLabel: string;
  placeholder?: string;
  voice: InterviewerVoice;
  extraActions?: ReactNode;
  maxLength: number;
  hint?: ReactNode;
  rows?: number;
  /** Id of the error shown under the composer (when there is one), so the answer box describes it. */
  errorId?: string;
  /** A click that sent nothing although nothing was visibly being sent (for diagnostics). */
  onIgnored?: () => void;
  /** Lets another control (the code editor's Ctrl/⌘+Enter) send through the same checks. */
  submitRef?: MutableRefObject<(() => void) | null>;
}) {
  const valueRef = useRef(value);
  useLayoutEffect(() => {
    valueRef.current = value;
  });
  const used = useRef({ typed: false, voice: false });
  // This take: the answer before Speak answer, and whether it was typed into since.
  const [take, setTake] = useState<{ before: string; typed: boolean; after: string | null } | null>(null);
  const append = (text: string) => {
    used.current.voice = true;
    const current = valueRef.current;
    const next = (current && !/\s$/.test(current) ? `${current} ` : current) + text;
    valueRef.current = next; // two phrases in one event both land, not just the second
    onChange(next);
  };
  const dictation = useDictation(append);
  const elapsed = useElapsed(dictation.startedAt);
  const sending = useRef<string | null>(null); // the text being sent, or just sent
  const sendingSince = useRef(0);

  // A fresh, empty answer box (e.g. the next question) starts with a clean source record.
  useEffect(() => {
    if (!value) used.current = { typed: false, voice: false };
    if (sending.current !== null && value !== sending.current) sending.current = null;
  }, [value]);
  // Never transcribe the interviewer: if playback starts, stop listening.
  useEffect(() => {
    if (voice.speaking && dictation.state === "listening") dictation.cancel();
  }, [voice.speaking, dictation]);
  // Leaving the question (disabled) or the page stops the microphone.
  useEffect(() => {
    if (disabled) dictation.cancel();
  }, [disabled, dictation]);

  const micOn = dictation.state === "listening";
  const busyMic = micOn || dictation.state === "processing";
  const status = voice.speaking ? "Interviewer speaking" : STATE_TEXT[dictation.state];
  // When this take ends, remember what it left, so Discard is offered only until the answer changes.
  useEffect(() => {
    if (!busyMic) setTake((t) => (t && t.after === null ? { ...t, after: valueRef.current } : t));
  }, [busyMic]);
  const canDiscard = !!take && !take.typed && (busyMic || value === take.after) && value !== take.before;

  function talk() {
    if (voice.speaking) voice.stop();
    if (dictation.state === "error" || dictation.state === "denied") dictation.reset();
    setTake({ before: valueRef.current, typed: false, after: null });
    dictation.start();
  }

  function discard() {
    if (!take) return;
    dictation.cancel();
    dictation.dismissUnconfirmed();
    valueRef.current = take.before;
    onChange(take.before);
    setTake(null);
  }

  function addUnconfirmed() {
    append(dictation.unconfirmed);
    dictation.dismissUnconfirmed();
  }

  function submit(e?: FormEvent) {
    e?.preventDefault();
    // Held for seconds while nothing is visibly being sent: the box looks ready but won't send.
    if (sending.current !== null && !submitting && performance.now() - sendingSince.current > 3000) onIgnored?.();
    if (sending.current !== null || submitting || busyMic || disabled || !value.trim()) return;
    const text = value;
    sending.current = text;
    sendingSince.current = performance.now();
    const { typed, voice: spoke } = used.current;
    const release = () => { if (sending.current === text) sending.current = null; };
    onSubmit(spoke && typed ? "mixed" : spoke ? "voice" : "typed").then((sent) => { if (!sent) release(); }, release);
  }
  useLayoutEffect(() => {
    if (submitRef) submitRef.current = () => submit();
  });

  return (
    <form className="card stack voice-composer" onSubmit={submit} onKeyDown={(e) => { if (e.key === "Escape" && busyMic) { e.preventDefault(); dictation.stop(); } }}>
      <div className="voice-composer__head">
        <h2 className="section-title" id={`${id}-label`}>{label}</h2>
        <span className="voice-composer__state">
          <p className={`voice-status voice-status--${voice.speaking ? "speaking" : dictation.state}`} role="status">
            <span className="voice-status__dot" aria-hidden="true" />
            {status}
          </p>
          {/* Outside the status: a ticking time isn't announced every second. */}
          {micOn && elapsed !== null && <span className="voice-elapsed subtle">{formatElapsed(elapsed)}</span>}
        </span>
      </div>
      <textarea id={id} aria-labelledby={`${id}-label`} aria-describedby={errorId ? `${id}-help ${errorId}` : `${id}-help`} className="input answer-input" rows={rows}
        maxLength={maxLength} value={value} disabled={disabled} readOnly={submitting} aria-busy={submitting || undefined} placeholder={placeholder}
        onChange={(e) => { used.current.typed = true; setTake((t) => (t ? { ...t, typed: true } : t)); onChange(e.target.value); }}
        onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); submit(); } }} />
      {dictation.interim && (
        <p className="voice-interim" aria-live="off"><span className="voice-interim__tag">Hearing (not final yet)</span> {dictation.interim}</p>
      )}
      {dictation.error && <p className="banner banner--warning" role="alert">{dictation.error}</p>}
      {dictation.notice && <p className="subtle voice-notice" aria-live="polite">{dictation.notice}</p>}
      {voice.problem && (
        <p className="subtle voice-notice" aria-live="polite">
          {voice.problem} <Button type="button" size="sm" variant="ghost" onClick={voice.dismissProblem}>Dismiss</Button>
        </p>
      )}
      {dictation.unconfirmed && !busyMic && (
        <div className="voice-unconfirmed" role="group" aria-label="Words that weren't confirmed">
          <p>These words were heard but not confirmed before listening stopped: <q>{dictation.unconfirmed}</q></p>
          <span className="row">
            <Button type="button" size="sm" onClick={addUnconfirmed}>Add them to my answer</Button>
            <Button type="button" size="sm" variant="ghost" onClick={dictation.dismissUnconfirmed}>Leave them out</Button>
          </span>
        </div>
      )}
      <div className="answer-actions">
        <span id={`${id}-help`} className="subtle">
          {busyMic ? "Stop the microphone to review your answer before sending. Esc also stops it." : hint}
        </span>
        <span className="row voice-composer__buttons">
          {voice.speaking && <Button type="button" variant="ghost" onClick={voice.stop}>Stop interviewer</Button>}
          {canDiscard && (
            <Button type="button" variant="ghost" onClick={discard} disabled={disabled}>
              {busyMic ? "Discard this take" : "Discard last take"}
            </Button>
          )}
          {dictation.supported && (micOn ? (
            <Button type="button" variant="primary" disabled={disabled} onClick={dictation.stop}>
              <Icon name="stop" size={15} />Stop listening
            </Button>
          ) : (
            <Button type="button" variant="secondary" disabled={disabled || dictation.state === "processing"} onClick={talk}>
              <Icon name="mic" size={15} />{dictation.state === "denied" ? "Try the microphone again" : "Speak answer"}
            </Button>
          ))}
          {extraActions}
          <Button type="submit" variant="primary" loading={submitting} disabled={disabled || busyMic || !value.trim()}>
            {submitLabel}
          </Button>
        </span>
      </div>
      {!dictation.supported && (
        <p className="subtle">Speaking your answer needs speech recognition, which this browser doesn't offer (Chrome, Edge and Safari do). Typing works everywhere.</p>
      )}
    </form>
  );
}

/** Seconds since `startedAt`, ticking once a second; null when not listening. */
function useElapsed(startedAt: number | null): number | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (startedAt === null) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [startedAt]);
  return startedAt === null ? null : Math.max(0, Math.floor((now - startedAt) / 1000));
}

const formatElapsed = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
