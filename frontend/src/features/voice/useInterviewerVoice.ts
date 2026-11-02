import { useCallback, useEffect, useRef, useState } from "react";

import { canSpeak } from "./capabilities";
import type { VoicePrefs } from "./voicePrefs";

/**
 * The interviewer's voice (the browser's speech synthesis). `speaking` is true from the moment
 * playback starts until it ends or is stopped, so dictation can refuse to listen meanwhile and the
 * interviewer is never transcribed as the learner.
 */
export function useInterviewerVoice(prefs: VoicePrefs) {
  const supported = canSpeak();
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [speaking, setSpeaking] = useState(false);
  const [caption, setCaption] = useState<string | null>(null);
  const current = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    if (!supported) return;
    const synth = window.speechSynthesis;
    const load = () => setVoices(synth.getVoices());
    load();
    synth.addEventListener?.("voiceschanged", load);
    return () => {
      synth.removeEventListener?.("voiceschanged", load);
      synth.cancel(); // leaving the page stops the interviewer
    };
  }, [supported]);

  const stop = useCallback(() => {
    if (!supported) return;
    current.current = null;
    window.speechSynthesis?.cancel();
    setSpeaking(false);
    setCaption(null);
  }, [supported]);

  const speak = useCallback(
    (text: string) => {
      if (!supported || !text.trim()) return;
      window.speechSynthesis.cancel();
      const u = new window.SpeechSynthesisUtterance(text);
      const voice = voices.find((v) => v.voiceURI === prefs.voiceURI);
      if (voice) u.voice = voice;
      u.rate = prefs.rate;
      u.volume = prefs.volume;
      const done = () => {
        if (current.current !== u) return; // a newer utterance (or stop) took over
        current.current = null;
        setSpeaking(false);
        setCaption(null);
      };
      u.onend = done;
      u.onerror = done;
      current.current = u;
      setSpeaking(true);
      setCaption(text);
      window.speechSynthesis.speak(u);
    },
    [supported, voices, prefs.voiceURI, prefs.rate, prefs.volume],
  );

  return { supported, voices, speaking, caption, speak, stop };
}

export type InterviewerVoice = ReturnType<typeof useInterviewerVoice>;
