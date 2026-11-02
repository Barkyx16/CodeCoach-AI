import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { recognitionCtor, type RecognitionLike } from "./capabilities";

/**
 * Push-to-talk dictation with the browser's speech recognition.
 *
 *   ready ──start──▶ listening ──stop──▶ processing ──(final text flushed)──▶ ready
 *                       │  └─(browser ends after silence)──────────────────▶ ready
 *                       └─error──▶ denied | error (recoverable) | unavailable
 *
 * Final phrases are handed to `onFinal` (the caller appends them to the editable draft); interim
 * text is exposed separately and never written into the draft. Nothing is ever submitted from
 * here. Callbacks from an earlier session are ignored (each session has its own generation), so a
 * late result can't land twice.
 */
export type DictationState = "ready" | "listening" | "processing" | "unavailable" | "denied" | "error";

const STOP_TIMEOUT_MS = 4000;

const ERROR_MESSAGES: Record<string, string> = {
  "no-speech": "Didn't hear anything. Try again, or type your answer.",
  "audio-capture": "No microphone was found. Check it's connected, or type your answer.",
  network: "Your browser's speech service couldn't be reached. Check your connection, or type your answer.",
  "language-not-supported": "Speech recognition doesn't support your browser's language. Type your answer instead.",
};

export function useDictation(onFinal: (text: string) => void) {
  const Ctor = recognitionCtor();
  const [state, setState] = useState<DictationState>(Ctor ? "ready" : "unavailable");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognition = useRef<RecognitionLike | null>(null);
  const generation = useRef(0);
  const stopTimer = useRef<number | null>(null);
  const onFinalRef = useRef(onFinal);
  useLayoutEffect(() => {
    onFinalRef.current = onFinal;
  });

  const clearStopTimer = () => {
    if (stopTimer.current !== null) window.clearTimeout(stopTimer.current);
    stopTimer.current = null;
  };

  const end = useCallback((gen: number) => {
    if (gen !== generation.current) return;
    clearStopTimer();
    recognition.current = null;
    setInterim("");
    setState((s) => (s === "listening" || s === "processing" ? "ready" : s));
  }, []);

  const start = useCallback(() => {
    if (!Ctor || recognition.current) return;
    const gen = ++generation.current;
    const r = new Ctor();
    r.lang = navigator.language || "en-US";
    r.continuous = true;
    r.interimResults = true;
    r.onresult = (e) => {
      if (gen !== generation.current) return;
      let pending = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const result = e.results[i]!;
        const text = result[0]?.transcript ?? "";
        if (result.isFinal) {
          if (text.trim()) onFinalRef.current(text.trim());
        } else {
          pending += text;
        }
      }
      setInterim(pending.trim());
    };
    r.onerror = (e) => {
      if (gen !== generation.current || e.error === "aborted") return;
      clearStopTimer();
      recognition.current = null;
      setInterim(""); // unconfirmed speech is dropped, never submitted; the draft is untouched
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        setState("denied");
        setError("Microphone access is blocked. Allow it in your browser's site settings, or type your answer.");
      } else {
        setState("error");
        setError(ERROR_MESSAGES[e.error] ?? "Speech recognition stopped unexpectedly. Your text is kept; try again or type.");
      }
    };
    r.onend = () => end(gen);
    recognition.current = r;
    setError(null);
    setInterim("");
    setState("listening");
    try {
      r.start();
    } catch {
      recognition.current = null;
      setState("error");
      setError("Couldn't start the microphone. Try again, or type your answer.");
    }
  }, [Ctor, end]);

  /** Stop listening; final words still arriving are kept. Falls back to aborting if the browser hangs. */
  const stop = useCallback(() => {
    const r = recognition.current;
    if (!r) return;
    const gen = generation.current;
    setState("processing");
    try {
      r.stop();
    } catch {
      end(gen);
    }
    clearStopTimer();
    stopTimer.current = window.setTimeout(() => {
      if (gen !== generation.current) return;
      recognition.current?.abort();
      end(gen);
    }, STOP_TIMEOUT_MS);
  }, [end]);

  /** Stop immediately and discard anything not yet final (leaving the page, closing, etc.). */
  const cancel = useCallback(() => {
    generation.current++;
    clearStopTimer();
    recognition.current?.abort();
    recognition.current = null;
    setInterim("");
    setState((s) => (s === "listening" || s === "processing" ? "ready" : s));
  }, []);

  const reset = useCallback(() => {
    setError(null);
    setState(Ctor ? "ready" : "unavailable");
  }, [Ctor]);

  useEffect(() => () => {
    generation.current++;
    clearStopTimer();
    recognition.current?.abort();
  }, []);

  return { supported: !!Ctor, state, interim, error, start, stop, cancel, reset };
}

export type Dictation = ReturnType<typeof useDictation>;
