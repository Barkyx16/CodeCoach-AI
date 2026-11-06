import { Button } from "@/components/Button";

import { recognitionCtor } from "./capabilities";
import { useInterviewerVoice } from "./useInterviewerVoice";
import { useMicTest } from "./useMicTest";
import type { VoicePrefs } from "./voicePrefs";

const PERMISSION_TEXT = {
  granted: "Allowed",
  denied: "Blocked in this browser",
  prompt: "Not asked yet",
  unknown: "Not asked yet (or your browser doesn't report it)",
} as const;

function levelWord(level: number): string {
  return level < 8 ? "silent" : level < 35 ? "quiet" : level < 85 ? "good" : "loud";
}

/**
 * Pre-interview readiness: microphone status and test, the interviewer's voice, playback speed and
 * volume, captions, and what is recorded or sent. Nothing asks for the microphone until the user
 * clicks "Enable microphone".
 */
export function VoiceSetup({ prefs, onChange }: { prefs: VoicePrefs; onChange: (patch: Partial<VoicePrefs>) => void }) {
  const mic = useMicTest();
  const voice = useInterviewerVoice(prefs);
  const recognition = !!recognitionCtor();
  const englishFirst = [...voice.voices].sort((a, b) => Number(b.lang.startsWith("en")) - Number(a.lang.startsWith("en")));

  return (
    <section className="card stack voice-setup" aria-labelledby="voice-setup-title">
      <h2 className="section-title" id="voice-setup-title">Voice (optional)</h2>
      <p className="subtle">Answer out loud and have the interviewer read questions to you. You can always type instead.</p>

      <dl className="voice-setup__status">
        <div><dt>Microphone permission</dt><dd>{PERMISSION_TEXT[mic.permission]}</dd></div>
        <div><dt>Speech-to-text</dt><dd>{recognition ? "Available (your browser's speech recognition)" : "Not available in this browser. Chrome, Edge and Safari support it; you can type your answers."}</dd></div>
        <div><dt>Interviewer voice</dt><dd>{voice.supported ? `${voice.voices.length || "Default"} voice${voice.voices.length === 1 ? "" : "s"} available` : "Not available in this browser"}</dd></div>
      </dl>

      {mic.supported && (
        <div className="stack voice-setup__mic">
          <div className="row">
            {mic.testing
              ? <Button variant="secondary" onClick={mic.stopTest}>Stop microphone test</Button>
              : <Button variant="secondary" onClick={() => void mic.enable()}>Enable microphone and test</Button>}
          </div>
          {mic.level !== null && (
            <div className="voice-level">
              <label htmlFor="mic-level">Input level</label>
              <meter id="mic-level" min={0} max={100} low={8} high={85} optimum={50} value={mic.level} />
              <span>{mic.level}% · {levelWord(mic.level)}</span>
              <span className="subtle">Say a sentence: the bar should move. This test is never recorded.</span>
            </div>
          )}
          {/* Announce the outcome once, not every level change. */}
          <p className="visually-hidden" role="status">{mic.testing ? (mic.heard ? "Microphone test: we can hear you." : "Microphone test running. Say a sentence.") : ""}</p>
          {mic.error && <p className="banner banner--warning" role="alert">{mic.error}</p>}
        </div>
      )}

      {voice.supported && (
        <fieldset className="field voice-setup__voice">
          <legend className="field__label">Interviewer voice</legend>
          <label className="checkbox">
            <input type="checkbox" checked={prefs.readAloud} onChange={(e) => onChange({ readAloud: e.target.checked })} />
            Read each question aloud
          </label>
          <div className="voice-setup__grid">
            <label className="field">
              <span className="field__label">Voice</span>
              <select className="select" value={prefs.voiceURI ?? ""} onChange={(e) => onChange({ voiceURI: e.target.value || null })}>
                <option value="">Browser default</option>
                {englishFirst.map((v) => <option key={v.voiceURI} value={v.voiceURI}>{v.name} ({v.lang})</option>)}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Speed: {prefs.rate.toFixed(1)}×</span>
              <input type="range" min={0.7} max={1.4} step={0.1} value={prefs.rate} onChange={(e) => onChange({ rate: Number(e.target.value) })} />
            </label>
            <label className="field">
              <span className="field__label">Volume: {Math.round(prefs.volume * 100)}%</span>
              <input type="range" min={0} max={1} step={0.1} value={prefs.volume} onChange={(e) => onChange({ volume: Number(e.target.value) })} />
            </label>
          </div>
          <div className="row">
            <Button variant="ghost" size="sm" onClick={() => voice.speaking ? voice.stop() : voice.speak("Hi, thanks for joining. Tell me a little about yourself.")}>
              {voice.speaking ? "Stop sample" : "Play a sample"}
            </Button>
          </div>
        </fieldset>
      )}

      <fieldset className="field">
        <legend className="field__label">During the interview</legend>
        <label className="checkbox">
          <input type="checkbox" checked={prefs.captions} onChange={(e) => onChange({ captions: e.target.checked })} />
          Show captions of what the interviewer says
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={prefs.showEngagement} onChange={(e) => onChange({ showEngagement: e.target.checked })} />
          Show simulated interviewer engagement (you can review it afterwards either way)
        </label>
      </fieldset>

      <details className="voice-setup__privacy">
        <summary>What's recorded, sent and kept</summary>
        <ul className="mini-list">
          <li>CodeCoach never records or stores audio. The microphone test runs only in this page.</li>
          <li>Speech-to-text is done by your browser. In Chrome and Edge your speech is sent to the browser maker's speech service to be transcribed; Safari may do it on your device.</li>
          <li>Only the text you submit is sent to CodeCoach. It's saved with your interview, marked typed or spoken, and included in your data export and deletion.</li>
          <li>The interviewer's voice is generated by your browser from the question text.</li>
          <li>These settings are saved in this browser only.</li>
        </ul>
      </details>
    </section>
  );
}
