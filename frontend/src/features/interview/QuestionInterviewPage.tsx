import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { useStartInterview } from "@/api/queries";
import type { Difficulty } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/States";
import { titleCase } from "@/lib/format";
import { usePracticeTrack } from "@/features/careers/practiceTrack";
import { VoiceSetup } from "@/features/voice/VoiceSetup";
import { useVoicePrefs } from "@/features/voice/voicePrefs";

const LEVELS: Difficulty[] = ["easy", "medium", "hard"];
const DURATIONS = [10, 15, 20];

/**
 * Set up a mock interview made of the user's own career questions. The round itself is a server
 * session (/interviews/:id): it survives reloads, keeps a real deadline and appears in history.
 */
export function QuestionInterviewPage() {
  const { track, career } = usePracticeTrack();
  const navigate = useNavigate();
  const start = useStartInterview();
  const [prefs, setPrefs] = useVoicePrefs();
  const [level, setLevel] = useState<Difficulty>("easy");
  const [minutes, setMinutes] = useState(15);
  const role = career?.title ?? titleCase(track);
  const activeId = start.error instanceof ApiError && start.error.code === "interview_in_progress"
    ? (start.error.details as { interview_id?: string } | null)?.interview_id ?? null
    : null;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      const iv = await start.mutateAsync({ kind: "questions", track, difficulty: level, duration_minutes: minutes });
      navigate(`/interviews/${iv.id}`);
    } catch {
      /* shown below */
    }
  }

  return (
    <div className="page interview-start">
      <div className="page__header">
        <div>
          <p className="eyebrow">MOCK INTERVIEW</p>
          <h1 className="page__title">{role} interview</h1>
          <p className="page__subtitle">Five questions from {role} interviews, one at a time, the way an interviewer would ask them.</p>
        </div>
      </div>
      <div className="interview-start__grid">
        <Card className="stack">
          <p className="interview-start__lead">How it works</p>
          <ol className="mini-list mini-list--numbered">
            <li>Why this job, what you know, situations you'd handle, times you did it, and leading others, depending on the level.</li>
            <li>Answer each one as you would out loud, by speaking or typing. Aim for 2-3 minutes and 120-350 words.</li>
            <li>Each answer is scored when you submit it and saved to your practice.</li>
            <li>At the end you get every score, what you covered and what to add.</li>
          </ol>
          <p className="subtle">The timer runs on the server from the moment you start. It keeps running if you leave the page, and it can't be paused.</p>
        </Card>
        <form className="card stack" onSubmit={onSubmit} aria-labelledby="round-setup">
          <h2 className="section-title" id="round-setup">Set up your interview</h2>
          <fieldset className="field">
            <legend className="field__label">Difficulty</legend>
            <div className="segmented">
              {LEVELS.map((l) => (
                <label key={l} className={`segmented__option${level === l ? " segmented__option--active" : ""}`}>
                  <input type="radio" name="level" value={l} checked={level === l} onChange={() => setLevel(l)} />
                  {titleCase(l)}
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="field">
            <legend className="field__label">Time limit</legend>
            <div className="segmented">
              {DURATIONS.map((d) => (
                <label key={d} className={`segmented__option${minutes === d ? " segmented__option--active" : ""}`}>
                  <input type="radio" name="duration" value={d} checked={minutes === d} onChange={() => setMinutes(d)} />
                  {d} min
                </label>
              ))}
            </div>
          </fieldset>
          {activeId ? (
            <div className="banner banner--warning" role="alert">
              You already have an interview in progress. <Link to={`/interviews/${activeId}`}>Resume it</Link>
            </div>
          ) : <InlineError error={start.error} />}
          <Button type="submit" variant="primary" loading={start.isPending}>Start interview</Button>
          <p className="subtle">Want to work on one question at a time? <Link to="/problems?view=questions">Browse all {role} questions</Link>.</p>
        </form>
      </div>
      <VoiceSetup prefs={prefs} onChange={setPrefs} />
    </div>
  );
}
