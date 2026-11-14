# Voice in interviews and drills (Volume 7, prompt 9)

Voice is optional. Every interview and drill can be done entirely by typing, and the written
question is always on the page, so a learner can finish a session without hearing or saying
anything. There is one audio stack: the browser's own speech recognition (dictation) and speech
synthesis (the interviewer's voice). CodeCoach records no audio.

## What each browser offers

| Capability | Chrome / Edge (desktop, Android) | Safari (macOS, iOS) | Firefox | What the app shows without it |
|---|---|---|---|---|
| Dictation (`SpeechRecognition`) | yes; speech is sent to the browser maker's speech service | yes, when Siri & Dictation is on; may run on the device | no | "Voice input unavailable" and a typing note; no Speak button |
| Interviewer voice (`speechSynthesis`) | yes | yes | yes | no read-aloud buttons; the question is written |
| Microphone test (`getUserMedia`, setup page) | yes | yes | yes | the test is left out |

This table comes from the browsers' documentation and the app's feature checks
(`features/voice/capabilities.ts`). It wasn't checked on real devices for this change (see Limits).

## The controls

- **Speak answer** starts the microphone. Only a click (or Enter on the focused button) starts it:
  never a page load, a resume, a new question or a timer.
- **Stop listening** (or Esc in the answer box) stops it. Words still being recognised are kept.
- **Discard this take** throws away everything added since Speak answer and puts the answer back
  as it was. After the take ends it's offered as **Discard last take**, until the answer is edited.
- While listening, the status says "Listening. Microphone on" and the time listened is shown next
  to it. The time sits outside the announced status, so a screen reader isn't interrupted every
  second. The status dot pulses only while listening, and not at all with reduced motion (the
  device setting or Settings → Display).
- Send is disabled while the microphone is on or still processing, in interviews and drills. The
  coding interview's Ctrl/⌘+Enter in the editor goes through the same checks. It used to send
  partial dictation, always marked typed.

## The transcript

- Recognised (final) phrases are appended to the answer box, which stays editable. Unconfirmed
  (interim) words are shown apart, under "Hearing (not final yet)", and never sent.
- Each phrase lands once. A browser that sends earlier results again (some mobile builds do) doesn't
  duplicate them, and two phrases arriving together both land (one used to overwrite the other).
- A pause never sends anything. If the browser ends listening on its own (a long pause, a lost
  microphone), the page says so and keeps the words. Listening also stops when the tab goes into
  the background, and the page says so.
- When listening fails or ends with words still unconfirmed, they're offered back: **Add them to
  my answer** or **Leave them out**. They're never added unasked.
- What's evaluated is exactly the text in the box when the learner sends it, after any edits. There
  is no recording to compare it with. The answer is marked typed, spoken, or spoken and edited, for
  review only.

## When something goes wrong

| What happened | What the learner sees | The way on |
|---|---|---|
| Microphone permission refused | "Microphone access is blocked…" | **Try the microphone again** once it's allowed, on the same question; or type |
| Speech turned off on the device (`service-not-allowed`) | "Speech recognition is turned off for this browser or device…" | turn it on, or type |
| Microphone missing, unplugged, or in use (`audio-capture`) | "The microphone isn't available…"; recognised words kept; unconfirmed words offered | reconnect and press Speak answer |
| Speech service unreachable (`network`) | says so; words kept | try again, or type |
| Nothing heard (`no-speech`) | says so | try again, or type |
| The interviewer's voice fails | "The interviewer's voice couldn't play. Everything it says is written on the page." | read it; replay with the read-aloud button |
| Read aloud is on, but the page was just reloaded (no interaction yet) | it doesn't play, and says why | the read-aloud button |
| A browser never reports the end of speech | "Interviewer speaking" clears after a generous limit | — |
| The microphone test is unplugged, or the page closes while the browser is still asking | the test stops and releases the microphone | test again |

## The simulated engagement cue

"Simulated interviewer engagement" is worked out on the server from the answer's words only, using
the practice rubric (relevance, specific examples, structure, detail). It takes no audio, timing or
input method. It isn't a real person's reaction, it doesn't read emotion or tone, and it doesn't
predict hiring. The card says this every time it's shown.

- Every state has a distinct shape and a text label. All states use neutral text colours, so the
  cue doesn't read as a red or green light. It changes only when an answer is sent, never while
  the learner speaks.
- It can be hidden during an interview (Hide), on the question-interview start page, or in
  **Settings → Display & reading → Interview voice and cues**, for every career. Hiding it changes
  nothing about practice, scoring or feedback; the results page still shows it.
- The actual assessment, the rubric score and feedback, is separate from the cue and is the same
  for typed and spoken answers: `test_the_same_answer_typed_or_spoken_gets_the_same_evaluation`
  sends one answer typed and one spoken through the API and compares score, feedback and
  engagement. Drills now evaluate typed and spoken text the same way too: filler sounds are left
  out of both. Before, only spoken answers had them removed.
- Spoken delivery (pace, accent, tone) is never measured. The review says "not measured" when
  something was spoken, and "not applicable" when everything was typed. The coding review used to
  say "not measured" even for all-typed interviews.

## Privacy

- No audio is recorded, uploaded or stored by CodeCoach. The microphone test analyses the level in
  the page and keeps nothing.
- In Chrome and Edge, dictation sends speech to the browser maker's speech service; Safari may
  transcribe on the device. This is the browser's processing, under the browser's terms; CodeCoach
  receives only the text the learner sends.
- The interviewer's voice is generated by the browser from the question text.
- Voice settings (read aloud, captions, the cue, voice and rate) are kept in this browser only.

## Tests

- `frontend/src/test/integration/voiceInterview.test.tsx`: 12 new checks plus the existing ones (22).
  - Two phrases in one event; a re-sent phrase isn't duplicated.
  - Elapsed time outside the live status; Discard during and after a take.
  - A lost microphone keeps the words, offers the unconfirmed ones, and the interview goes on.
  - Unconfirmed words can be left out.
  - A blocked microphone is retried; speech turned off is told apart.
  - Listening ending on its own, or when the tab is hidden.
  - Leaving the page releases the microphone.
  - Nothing listens or plays on resume.
  - Loading voices doesn't restart the question.
  - Playback failure is said; a deliberate stop isn't a failure.
  - The cue is hidden from Settings.
- `drills.test.tsx` and `e2e/drills.spec.ts`: "The microphone was on for N seconds, pauses included".
- Backend:
  - `test_question_rounds.py`: typed and spoken parity through the API, replacing a test that
    compared a function with itself.
  - `test_drills.py`: drill parity.
  - `test_review.py`: spoken delivery, typed and spoken.
- `frontend/e2e/voice-recovery.spec.ts` (Chromium, real API, a stand-in recogniser):
  - **The demonstration**: a microphone is lost mid-answer and the learner recovers on the same
    question; screenshots in `frontend/e2e/screenshots/voice-mic-lost.png` and
    `voice-recovered.png`.
  - It also covers keyboard start and Esc stop, reduced motion (no pulse) and axe on the composer.
  - The coding editor's shortcut doesn't send while listening, and sends "voice" after.
- Negative controls (each mutation applied alone, then reverted), each caught:
  - the value not updated between phrases;
  - no index de-duplication;
  - `speak` changing with the voice list;
  - unconfirmed words dropped on an error;
  - auto-play without interaction;
  - drills cleaning only spoken text.

## Limits

- **Not run here:** real microphones and devices, real browser speech services, and screen readers
  (NVDA, JAWS, VoiceOver, TalkBack). The recogniser in the tests is a stand-in, because Chromium's
  needs Google's service.
- **A screen reader may speak over the interviewer.** In the coding interview the transcript is a
  polite live region, so a screen reader can announce a message while the interviewer's voice reads
  it. Turning Read aloud off avoids it.
- **After a reload, a dictated draft is sent as typed.** The typed/spoken flags live in the page, not
  with the stored draft. This affects only the review label, never the score.
- **There's no Pause.** Stop, then Speak answer again, appends to the same answer.
- **Device removal is inferred.** Dictation can't watch the microphone track. A lost microphone shows
  up as the browser's `audio-capture` error or as listening ending on its own, and both are handled.
