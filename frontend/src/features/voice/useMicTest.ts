import { useCallback, useEffect, useRef, useState } from "react";

import { canTestMicrophone, microphonePermission, type MicPermission } from "./capabilities";

/**
 * Microphone check: asks for access only when `enable()` is called (a deliberate click), then
 * shows the input level. Audio is analysed in the page and never recorded or sent anywhere.
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

  useEffect(() => {
    void microphonePermission().then(setPermission);
  }, []);

  const stopTest = useCallback(() => {
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
    if (!supported) return;
    setError(null);
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = s;
      setPermission("granted");
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
  }, [supported]);

  useEffect(() => stopTest, [stopTest]);

  return { supported, permission, level, heard, testing: level !== null, error, enable, stopTest };
}
