import { useCallback, useState } from "react";

/** Per-device voice settings. Stored in this browser only (they're conveniences, not account data). */
export interface VoicePrefs {
  voiceURI: string | null;
  rate: number; // 0.7-1.4
  volume: number; // 0-1
  readAloud: boolean; // the interviewer reads each question aloud
  captions: boolean; // show what the interviewer is saying as a caption
  showEngagement: boolean; // show the simulated engagement indicator during the interview
}

export const DEFAULT_VOICE_PREFS: VoicePrefs = {
  voiceURI: null,
  rate: 1,
  volume: 1,
  readAloud: false,
  captions: true,
  showEngagement: true,
};

const KEY = "codecoach.voice";

const inRange = (v: unknown, min: number, max: number): v is number => typeof v === "number" && Number.isFinite(v) && v >= min && v <= max;

/**
 * Saved values are checked one by one; anything of the wrong type or out of range falls back to the
 * default. (A hand-edited or corrupted value must never, say, turn on reading aloud.)
 */
export function parseVoicePrefs(raw: string | null): VoicePrefs {
  let saved: Record<string, unknown> = {};
  try {
    const value: unknown = JSON.parse(raw ?? "null");
    if (value && typeof value === "object" && !Array.isArray(value)) saved = value as Record<string, unknown>;
  } catch {
    return DEFAULT_VOICE_PREFS;
  }
  const bool = (key: "readAloud" | "captions" | "showEngagement") => (typeof saved[key] === "boolean" ? saved[key] : DEFAULT_VOICE_PREFS[key]);
  return {
    voiceURI: typeof saved.voiceURI === "string" && saved.voiceURI.length <= 500 ? saved.voiceURI : null,
    rate: inRange(saved.rate, 0.7, 1.4) ? saved.rate : DEFAULT_VOICE_PREFS.rate,
    volume: inRange(saved.volume, 0, 1) ? saved.volume : DEFAULT_VOICE_PREFS.volume,
    readAloud: bool("readAloud"),
    captions: bool("captions"),
    showEngagement: bool("showEngagement"),
  };
}

export function loadVoicePrefs(): VoicePrefs {
  try {
    return parseVoicePrefs(window.localStorage.getItem(KEY));
  } catch {
    return DEFAULT_VOICE_PREFS; // storage blocked
  }
}

export function useVoicePrefs(): [VoicePrefs, (patch: Partial<VoicePrefs>) => void] {
  const [prefs, setPrefs] = useState(loadVoicePrefs);
  const update = useCallback((patch: Partial<VoicePrefs>) => {
    setPrefs((current) => {
      const next = { ...current, ...patch };
      try {
        window.localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        /* private mode: keep it for this page only */
      }
      return next;
    });
  }, []);
  return [prefs, update];
}
