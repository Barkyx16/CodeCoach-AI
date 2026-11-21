import { useVoicePrefs } from "./voicePrefs";

/**
 * Interview voice preferences in Settings, for every career (the question-interview start page has
 * the same choices plus a microphone test). Saved in this browser; the same values as there.
 */
export function VoiceSettings() {
  const [prefs, update] = useVoicePrefs();
  return (
    <fieldset className="field voice-settings">
      <legend className="visually-hidden">Interview voice and cues</legend>
      <label className="checkbox">
        <input type="checkbox" checked={prefs.readAloud} onChange={(e) => update({ readAloud: e.target.checked })} />
        Have the interviewer read each question aloud
      </label>
      <label className="checkbox">
        <input type="checkbox" checked={prefs.captions} onChange={(e) => update({ captions: e.target.checked })} />
        Show captions of what the interviewer says
      </label>
      <label className="checkbox">
        <input type="checkbox" checked={prefs.showEngagement} onChange={(e) => update({ showEngagement: e.target.checked })} />
        Show the simulated interviewer engagement cue during interviews
      </label>
      <p className="subtle">
        The engagement cue is a simulation worked out from what your answer says, using the practice rubric. It doesn't
        listen to your voice or tone, isn't a real person's reaction, and doesn't predict hiring. Hiding it changes nothing
        about your practice or feedback, and you can still see it on the results page.
      </p>
    </fieldset>
  );
}
