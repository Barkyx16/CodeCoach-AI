import { useEffect, useLayoutEffect, useRef, type FormEvent, type ReactNode } from "react";

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
 * - Recognised (final) phrases are appended to the editable draft; unconfirmed (interim) words
 *   are shown separately and never submitted.
 * - Submitting is disabled while the microphone is on or still processing, so partial speech is
 *   never sent; the learner stops, reviews, then submits.
 * - The microphone and the interviewer's voice never run together: talking stops playback, and
 *   playback starting cancels listening.
 * - `submitting` comes from the caller's request state; a ref also guards double submits.
 */
export function VoiceComposer({
  id, label, value, onChange, onSubmit, submitting, disabled = false, submitLabel, placeholder,
  voice, extraActions, maxLength, hint, rows = 8,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit: (source: AnswerSource) => void;
  submitting: boolean;
  disabled?: boolean;
  submitLabel: string;
  placeholder?: string;
  voice: InterviewerVoice;
  extraActions?: ReactNode;
  maxLength: number;
  hint?: ReactNode;
  rows?: number;
}) {
  const valueRef = useRef(value);
  useLayoutEffect(() => {
    valueRef.current = value;
  });
  const used = useRef({ typed: false, voice: false });
  const dictation = useDictation((text) => {
    used.current.voice = true;
    const current = valueRef.current;
    onChange((current && !/\s$/.test(current) ? `${current} ` : current) + text);
  });
  const sending = useRef(false);

  // A fresh, empty answer box (e.g. the next question) starts with a clean source record.
  useEffect(() => {
    if (!value) used.current = { typed: false, voice: false };
  }, [value]);
  useEffect(() => {
    if (!submitting) sending.current = false;
  }, [submitting]);
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

  function talk() {
    if (micOn) return dictation.stop();
    if (voice.speaking) voice.stop();
    if (dictation.state === "error" || dictation.state === "denied") dictation.reset();
    dictation.start();
  }

  function submit(e?: FormEvent) {
    e?.preventDefault();
    if (sending.current || submitting || busyMic || disabled || !value.trim()) return;
    sending.current = true;
    const { typed, voice: spoke } = used.current;
    onSubmit(spoke && typed ? "mixed" : spoke ? "voice" : "typed");
  }

  return (
    <form className="card stack voice-composer" onSubmit={submit} onKeyDown={(e) => { if (e.key === "Escape" && busyMic) { e.preventDefault(); dictation.stop(); } }}>
      <div className="voice-composer__head">
        <h2 className="section-title" id={`${id}-label`}>{label}</h2>
        <p className={`voice-status voice-status--${voice.speaking ? "speaking" : dictation.state}`} role="status">
          <span className="voice-status__dot" aria-hidden="true" />
          {status}
        </p>
      </div>
      <textarea id={id} aria-labelledby={`${id}-label`} aria-describedby={`${id}-help`} className="input answer-input" rows={rows}
        maxLength={maxLength} value={value} disabled={disabled} placeholder={placeholder}
        onChange={(e) => { used.current.typed = true; onChange(e.target.value); }}
        onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); submit(); } }} />
      {dictation.interim && (
        <p className="voice-interim" aria-live="off"><span className="voice-interim__tag">Hearing (not final yet)</span> {dictation.interim}</p>
      )}
      {dictation.error && <p className="banner banner--warning" role="alert">{dictation.error}</p>}
      <div className="answer-actions">
        <span id={`${id}-help`} className="subtle">
          {busyMic ? "Stop the microphone to review your answer before sending. Esc also stops it." : hint}
        </span>
        <span className="row voice-composer__buttons">
          {voice.speaking && <Button type="button" variant="ghost" onClick={voice.stop}>Stop interviewer</Button>}
          {dictation.supported && dictation.state !== "denied" && (
            <Button type="button" variant={micOn ? "primary" : "secondary"} aria-pressed={micOn}
              disabled={disabled || dictation.state === "processing"} onClick={talk}>
              <Icon name={micOn ? "stop" : "mic"} size={15} />{micOn ? "Stop listening" : "Speak answer"}
            </Button>
          )}
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
