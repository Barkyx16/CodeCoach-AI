import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { canSpeak } from "./capabilities";
import type { VoicePrefs } from "./voicePrefs";

/**
 * The interviewer's voice (the browser's speech synthesis). `speaking` is true from the moment
 * playback starts until it ends or is stopped, so dictation can refuse to listen meanwhile and the
 * interviewer is never transcribed as the learner.
 *
 * - One voice at a time: speaking again stops what was playing.
 * - `speak` keeps its identity when the voice list loads, so a question being read isn't cut off
 *   and started again (effects that read new questions depend on it).
 * - A failure is said (`problem`), with the written question as the way on; a browser that never
 *   reports the end is given up on after a generous time, so "Interviewer speaking" can't stick.
 * - `autoSpeak` (reading a new question because Read aloud is on) doesn't play before the learner
 *   has interacted with the page, e.g. right after a reload: browsers refuse that, so it says how
 *   to start it instead of failing silently.
 */
export function useInterviewerVoice(prefs: VoicePrefs) {
  const supported = canSpeak();
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [speaking, setSpeaking] = useState(false);
  const [caption, setCaption] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const current = useRef<SpeechSynthesisUtterance | null>(null);
  const watchdog = useRef<number | null>(null);
  const settings = useRef({ voices, prefs });
  useLayoutEffect(() => {
    settings.current = { voices, prefs };
  });

  const clearWatchdog = () => {
    if (watchdog.current !== null) window.clearTimeout(watchdog.current);
    watchdog.current = null;
  };

  useEffect(() => {
    if (!supported) return;
    const synth = window.speechSynthesis;
    const load = () => setVoices(synth.getVoices());
    load();
    synth.addEventListener?.("voiceschanged", load);
    return () => {
      synth.removeEventListener?.("voiceschanged", load);
      clearWatchdog();
      synth.cancel(); // leaving the page stops the interviewer
    };
  }, [supported]);

  const stop = useCallback(() => {
    if (!supported) return;
    current.current = null;
    clearWatchdog();
    window.speechSynthesis?.cancel();
    setSpeaking(false);
    setCaption(null);
  }, [supported]);

  const speak = useCallback(
    (text: string) => {
      if (!supported || !text.trim()) return;
      window.speechSynthesis.cancel();
      const { voices: list, prefs: p } = settings.current;
      const u = new window.SpeechSynthesisUtterance(text);
      const voice = list.find((v) => v.voiceURI === p.voiceURI);
      if (voice) u.voice = voice;
      u.rate = p.rate;
      u.volume = p.volume;
      const done = () => {
        if (current.current !== u) return; // a newer utterance (or stop) took over
        current.current = null;
        clearWatchdog();
        setSpeaking(false);
        setCaption(null);
      };
      u.onend = done;
      u.onerror = (e: { error?: string }) => {
        if (current.current !== u) return;
        done();
        // Stopping or replacing it isn't a failure; anything else is said, never swallowed.
        if (e?.error === "interrupted" || e?.error === "canceled") return;
        setProblem(e?.error === "not-allowed"
          ? "Your browser didn't let the interviewer speak yet. Use the read-aloud button to hear it; it's also written on the page."
          : "The interviewer's voice couldn't play. Everything it says is written on the page.");
      };
      current.current = u;
      setProblem(null);
      setSpeaking(true);
      setCaption(text);
      clearWatchdog();
      // About 150 words a minute at rate 1; give it twice that, and at least 20 seconds.
      const limit = Math.max(20_000, (text.split(/\s+/).length / 2.5 / Math.max(0.5, p.rate)) * 1000 * 2);
      watchdog.current = window.setTimeout(() => {
        if (current.current !== u) return;
        window.speechSynthesis.cancel();
        done();
      }, limit);
      window.speechSynthesis.speak(u);
    },
    [supported],
  );

  /** Read a new question because Read aloud is on: only once the learner has interacted with the page. */
  const autoSpeak = useCallback((text: string) => {
    const activation = (navigator as Navigator & { userActivation?: { hasBeenActive: boolean } }).userActivation;
    if (activation && !activation.hasBeenActive) {
      setProblem("Read aloud is on, but your browser plays speech only after you interact with the page. Use the read-aloud button to hear this one; it's also written on the page.");
      return;
    }
    speak(text);
  }, [speak]);

  const dismissProblem = useCallback(() => setProblem(null), []);

  return { supported, voices, speaking, caption, problem, speak, autoSpeak, stop, dismissProblem };
}

export type InterviewerVoice = ReturnType<typeof useInterviewerVoice>;
