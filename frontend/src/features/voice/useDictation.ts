import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { recognitionCtor, type RecognitionLike } from "./capabilities";

/**
 * Push-to-talk dictation with the browser's speech recognition.
 *
 *   ready ──start──▶ listening ──stop──▶ processing ──(final text flushed)──▶ ready
 *                       │  └─(browser ends on its own: a long pause, a lost mic)──▶ ready + notice
 *                       ├─(tab hidden)──▶ stop, as above, + notice
 *                       └─error──▶ denied | error (recoverable) | unavailable
 *
 * Final phrases are handed to `onFinal` (the caller appends them to the editable draft), each once:
 * a result index already committed in this session is never committed again (some browsers send
 * earlier final results again). Interim text is exposed separately and never written into the
 * draft; if listening fails or ends while words are still unconfirmed, they're offered back as
 * `unconfirmed`, for the learner to add or leave out. Nothing is ever submitted from here.
 * Callbacks from an earlier session are ignored (each session has its own generation).
 */
export type DictationState = "ready" | "listening" | "processing" | "unavailable" | "denied" | "error";

const STOP_TIMEOUT_MS = 4000;

const ERROR_MESSAGES: Record<string, string> = {
  "no-speech": "Didn't hear anything. Try again, or type your answer.",
  "audio-capture": "The microphone isn't available: it may be unplugged, switched off or in use by another app. What was recognised is kept. Reconnect it and press Speak answer, or type.",
  network: "Your browser's speech service couldn't be reached. What was recognised is kept. Check your connection, or type your answer.",
  "language-not-supported": "Speech recognition doesn't support your browser's language. Type your answer instead.",
  "service-not-allowed": "Speech recognition is turned off for this browser or device (on a Mac, for example, Siri & Dictation may be off). Turn it on, or type your answer.",
};
const BLOCKED = "Microphone access is blocked. Allow it in your browser's site settings, then press Try the microphone again, or type your answer.";
const ENDED = "Listening stopped on its own (after a long pause, or the microphone was lost). What was recognised is kept; press Speak answer to go on.";
const HIDDEN = "Listening stopped because this tab went into the background. What was recognised is kept; press Speak answer to go on.";

export function useDictation(onFinal: (text: string) => void) {
  const Ctor = recognitionCtor();
  const [state, setState] = useState<DictationState>(Ctor ? "ready" : "unavailable");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [unconfirmed, setUnconfirmed] = useState("");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const recognition = useRef<RecognitionLike | null>(null);
  const generation = useRef(0);
  const stopping = useRef(false); // the learner (or the page) asked to stop: an end is expected
  const interimRef = useRef("");
  const stopTimer = useRef<number | null>(null);
  const onFinalRef = useRef(onFinal);
  useLayoutEffect(() => {
    onFinalRef.current = onFinal;
  });

  const clearStopTimer = () => {
    if (stopTimer.current !== null) window.clearTimeout(stopTimer.current);
    stopTimer.current = null;
  };
  const setPending = useCallback((text: string) => {
    interimRef.current = text;
    setInterim(text);
  }, []);
  /** Words heard but never confirmed are offered back, never dropped silently or added unasked. */
  const keepUnconfirmed = useCallback(() => {
    if (interimRef.current.trim()) setUnconfirmed(interimRef.current.trim());
    setPending("");
  }, [setPending]);

  const end = useCallback((gen: number) => {
    if (gen !== generation.current) return;
    clearStopTimer();
    recognition.current = null;
    setStartedAt(null);
    keepUnconfirmed(); // still unconfirmed when it ended: the browser never finalised them
    if (!stopping.current) setNotice(ENDED);
    stopping.current = false;
    setState((s) => (s === "listening" || s === "processing" ? "ready" : s));
  }, [keepUnconfirmed]);

  const start = useCallback(() => {
    if (!Ctor || recognition.current) return;
    const gen = ++generation.current;
    const committed = new Set<number>();
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
          if (committed.has(i)) continue; // sent again by the browser: already in the draft
          committed.add(i);
          if (text.trim()) onFinalRef.current(text.trim());
        } else {
          pending += text;
        }
      }
      setPending(pending.trim());
    };
    r.onerror = (e) => {
      if (gen !== generation.current || e.error === "aborted") return;
      clearStopTimer();
      recognition.current = null;
      stopping.current = false;
      setStartedAt(null);
      keepUnconfirmed(); // the draft is untouched; unconfirmed words are offered, not added
      if (e.error === "not-allowed") {
        setState("denied");
        setError(BLOCKED);
      } else {
        setState("error");
        setError(ERROR_MESSAGES[e.error] ?? "Speech recognition stopped unexpectedly. What was recognised is kept; try again or type.");
      }
    };
    r.onend = () => end(gen);
    recognition.current = r;
    stopping.current = false;
    setError(null);
    setNotice(null);
    setUnconfirmed("");
    setPending("");
    setState("listening");
    setStartedAt(Date.now());
    try {
      r.start();
    } catch {
      recognition.current = null;
      setStartedAt(null);
      setState("error");
      setError("Couldn't start the microphone. Try again, or type your answer.");
    }
  }, [Ctor, end, keepUnconfirmed, setPending]);

  /** Stop listening; final words still arriving are kept. Falls back to aborting if the browser hangs. */
  const stop = useCallback(() => {
    const r = recognition.current;
    if (!r) return;
    const gen = generation.current;
    stopping.current = true;
    setState("processing");
    setStartedAt(null);
    try {
      r.stop();
    } catch {
      end(gen);
    }
    clearStopTimer();
    stopTimer.current = window.setTimeout(() => {
      if (gen !== generation.current) return;
      recognition.current?.abort();
      end(gen); // whatever was still unconfirmed is offered back, not lost
    }, STOP_TIMEOUT_MS);
  }, [end]);

  /** Stop immediately and discard anything not yet final (Discard, leaving the question or the page). */
  const cancel = useCallback(() => {
    generation.current++;
    clearStopTimer();
    stopping.current = false;
    recognition.current?.abort();
    recognition.current = null;
    setPending("");
    setStartedAt(null);
    setState((s) => (s === "listening" || s === "processing" ? "ready" : s));
  }, [setPending]);

  const reset = useCallback(() => {
    setError(null);
    setNotice(null);
    setState(Ctor ? "ready" : "unavailable");
  }, [Ctor]);

  const dismissUnconfirmed = useCallback(() => setUnconfirmed(""), []);

  // A tab in the background may lose the microphone without a word: stop cleanly instead, and say so.
  useEffect(() => {
    const onVisibility = () => {
      if (!document.hidden || !recognition.current || stopping.current) return;
      stop();
      setNotice(HIDDEN);
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [stop]);

  useEffect(() => () => {
    generation.current++;
    clearStopTimer();
    recognition.current?.abort();
  }, []);

  return {
    supported: !!Ctor, state, interim, error, notice, unconfirmed, startedAt,
    start, stop, cancel, reset, dismissUnconfirmed,
  };
}

export type Dictation = ReturnType<typeof useDictation>;
