import { useCallback, useEffect, useRef, useState } from "react";

import { canTestMicrophone, microphonePermission, type MicPermission } from "./capabilities";

/**
 * Microphone check: asks for access only when `enable()` is called (a deliberate click), then
 * shows the input level. Audio is analysed in the page and never recorded or sent anywhere.
 * The microphone is released on Stop, on leaving the page, and when it's unplugged; a stream that
 * arrives after the test was stopped (or the page left) is released at once, and a second click
 * while the browser is still asking does nothing.
 */
export function useMicTest() {
  const supported = canTestMicrophone();
  const [permission, setPermission] = useState<MicPermission>("unknown");
  const [level, setLevel] = useState<number | null>(null); // 0-100 while testing
  const [error, setError] = useState<string | null>(null);
  // Set once per test when speech-level input arrives: the one thing worth announcing (the level itself changes every frame).
  const [heard, setHeard] = useState(false);
  const stream = useRef<MediaStream | null>(null);
  const context = useRef<AudioContext | null>(null);
  const frame = useRef<number | null>(null);
  const attempt = useRef(0); // which enable() is current; a stop or unmount makes earlier ones stale
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    void microphonePermission().then(setPermission);
  }, []);

  const stopTest = useCallback(() => {
    attempt.current += 1;
    setStarting(false);
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    void context.current?.close().catch(() => undefined);
    context.current = null;
    setLevel(null);
    setHeard(false);
  }, []);

  const enable = useCallback(async () => {
    if (!supported || stream.current) return;
    const mine = ++attempt.current;
    setError(null);
    setStarting(true);
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (mine !== attempt.current) {
        s.getTracks().forEach((t) => t.stop()); // stopped, or the page left, while the browser asked
        return;
      }
      setStarting(false);
      stream.current = s;
      setPermission("granted");
      for (const track of s.getAudioTracks()) {
        track.addEventListener("ended", () => {
          if (stream.current !== s) return;
          stopTest();
          setError("The microphone was disconnected. Reconnect it and test again, or answer by typing.");
        });
      }
      const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctx) {
        setLevel(0);
        return;
      }
      const ctx = new Ctx();
      context.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      ctx.createMediaStreamSource(s).connect(analyser);
      const data = new Uint8Array(analyser.fftSize);
      const tick = () => {
        analyser.getByteTimeDomainData(data);
        let peak = 0;
        for (const v of data) peak = Math.max(peak, Math.abs(v - 128));
        const value = Math.min(100, Math.round((peak / 128) * 160));
        setLevel(value);
        if (value >= 35) setHeard(true);
        frame.current = requestAnimationFrame(tick);
      };
      tick();
    } catch (e) {
      if (mine !== attempt.current) return;
      setStarting(false);
      const name = (e as { name?: string }).name;
      if (name === "NotAllowedError" || name === "SecurityError") {
        setPermission("denied");
        setError("Microphone access was blocked. You can allow it in your browser's site settings, or answer by typing.");
      } else if (name === "NotFoundError") {
        setError("No microphone was found. You can still answer by typing.");
      } else {
        setError("The microphone couldn't be started. You can still answer by typing.");
      }
    }
  }, [supported, stopTest]);

  useEffect(() => stopTest, [stopTest]);

  return { supported, permission, level, heard, testing: level !== null, starting, error, enable, stopTest };
}
