import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { useInterviewFormats, useStartInterview } from "@/api/queries";
import type { Difficulty, InterviewFormatId } from "@/api/types";
import { ActionError } from "@/components/ActionError";
import { useRetryWait } from "@/hooks/useCountdown";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { titleCase } from "@/lib/format";
import { BrowseNote } from "@/features/careers/BrowseNote";
import { usePracticeTrack, withCareer } from "@/features/careers/practiceTrack";
import { VoiceSetup } from "@/features/voice/VoiceSetup";

import { FormatPicker } from "./FormatPicker";
import { ResumeCard } from "./ResumeCard";
import { conflictInterview } from "./resumeContext";
import { useActiveInterview } from "./useActiveInterview";
import { useVoicePrefs } from "@/features/voice/voicePrefs";

const LEVELS: Difficulty[] = ["easy", "medium", "hard"];
const DURATIONS = [10, 15, 20];

/**
 * Set up a mock interview made of the user's own career questions. The round itself is a server
 * session (/interviews/:id): it survives reloads, keeps a real deadline and appears in history.
 */
export function QuestionInterviewPage() {
  const { track, career, keep } = usePracticeTrack();
  const navigate = useNavigate();
  const start = useStartInterview();
  const [prefs, setPrefs] = useVoicePrefs();
  const [level, setLevel] = useState<Difficulty>("easy");
  const [minutes, setMinutes] = useState(15);
  const [chosenFormat, setFormat] = useState<InterviewFormatId>("mixed");
  const formats = useInterviewFormats(track, level);
  // A format that isn't available at this level falls back to the default instead of failing on start.
  const format: InterviewFormatId = formats.data?.find((f) => f.id === chosenFormat)?.available ? chosenFormat : "mixed";
  const role = career?.title ?? titleCase(track);
  const running = useActiveInterview();
  // A Start refused because one is already live (another tab or device): that one, with context.
  const conflict = start.error instanceof ApiError && start.error.code === "interview_in_progress"
    ? conflictInterview(start.error.details)
    : null;
  const activeId = conflict?.id ?? running?.id ?? null;
  // Busy or out of AI budget: only Start waits, for as long as the server said.
  const startWait = useRetryWait(start.error);
  const activeSummary = conflict ? conflict.summary : running;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      const iv = await start.mutateAsync({ kind: "questions", purpose: "practice", track, difficulty: level, duration_minutes: minutes, ...(format !== "mixed" ? { format } : {}) });
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
          <p className="subtle">Or practise decisions in a <Link to={withCareer("/scenarios", keep)}>branching scenario</Link>.</p>
          <BrowseNote what="mock interviews" back="/interviews" scope={`A round you start here is saved to your history as a ${role} interview.`} />
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
          <p className="subtle">The timer runs on the server from the moment you start. It keeps running if you leave the page, and it can't be paused. The format can't be changed once you start.</p>
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
          <FormatPicker track={track} level={level} value={format} onChange={setFormat} />
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
          {activeId ? <ResumeCard id={activeId} summary={activeSummary} alert={Boolean(conflict)} />
              : !start.isPending && <ActionError error={start.error} action="Starting the interview" repeatSafe />}
          <Button type="submit" variant="primary" loading={start.isPending} disabled={Boolean(activeId) || startWait > 0}>Start interview</Button>
          <p className="subtle">Want to work on one question at a time? <Link to={withCareer("/problems?view=questions", keep)}>Browse all {role} questions</Link>.</p>
        </form>
      </div>
      <VoiceSetup prefs={prefs} onChange={setPrefs} />
    </div>
  );
}
