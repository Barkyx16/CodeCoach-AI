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

export function loadVoicePrefs(): VoicePrefs {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? { ...DEFAULT_VOICE_PREFS, ...(JSON.parse(raw) as Partial<VoicePrefs>) } : DEFAULT_VOICE_PREFS;
  } catch {
    return DEFAULT_VOICE_PREFS;
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
