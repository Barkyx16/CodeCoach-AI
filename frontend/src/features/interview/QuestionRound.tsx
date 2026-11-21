import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { queryKeys, useAbandonInterview, useAnswerRoundQuestion, useCapabilities, useSkipRoundQuestion } from "@/api/queries";
import type { AnswerSource, Difficulty, Interview } from "@/api/types";
import { Badge, DifficultyBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Icon } from "@/components/Icon";
import { InlineError } from "@/components/States";
import { useOnline } from "@/hooks/useOnline";
import { clearStoredDraft, readStoredDraft, useStoredDraft } from "@/hooks/useStoredDraft";
import { Link } from "react-router-dom";
import { titleCase } from "@/lib/format";
import { KIND_LABEL } from "@/features/careers/kinds";
import { FocusToggle } from "@/features/display/FocusToggle";
import { EngagementMeter } from "@/features/voice/EngagementMeter";
import { useInterviewerVoice } from "@/features/voice/useInterviewerVoice";
import { VoiceComposer } from "@/features/voice/VoiceComposer";
import { useVoicePrefs } from "@/features/voice/voicePrefs";

import { FollowupTurn } from "./FollowupTurn";
import { roundDraftKey } from "./roundDrafts";
import { reportIgnored, tracedRoundAction, useRoundViewDiag } from "./roundDiag";
import { setUiTelemetryEnabled } from "@/lib/uiTelemetry";
import { formatClock, useCountdown } from "./useCountdown";


function words(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

/** A question round in progress: one question at a time, spoken or typed, with simulated engagement. */
export function LiveRound({ iv }: { iv: Interview }) {
  const queryClient = useQueryClient();
  const online = useOnline();
  const [prefs, setPrefs] = useVoicePrefs();
  const voice = useInterviewerVoice(prefs);
  const current = iv.questions.find((q) => q.status === "current") ?? null;
  const pending = iv.round_format?.pending_followup ?? null;
  const roles = iv.round_format?.roles ?? [];
  const format = iv.round_format;
  const index = current?.index ?? pending?.question_index ?? 0;
  const [draft, setDraft] = useStoredDraft(roundDraftKey(iv.id, index));
  const answer = useAnswerRoundQuestion(iv.id);
  const skip = useSkipRoundQuestion(iv.id);
  const abandon = useAbandonInterview(iv.id);
  const seconds = useCountdown(iv.deadline_at, true);
  const heading = useRef<HTMLHeadingElement>(null);
  const busy = answer.isPending || skip.isPending || abandon.isPending;
  const role = iv.career_title ?? titleCase(iv.track ?? "");
  const last = [...iv.turns].reverse().find((t) => t.role === "candidate" && t.engagement)?.engagement ?? null;
  const error = answer.error ?? skip.error ?? abandon.error;
  // Report how actions ended on screen only when this server allows it.
  const telemetry = useCapabilities().data?.ui_telemetry ?? false;
  useEffect(() => setUiTelemetryEnabled(telemetry), [telemetry]);

  // When the clock runs out, ask the server: it closes the round and the results page shows.
  useEffect(() => {
    if (seconds === 0) void queryClient.invalidateQueries({ queryKey: queryKeys.interview(iv.id) });
  }, [seconds, iv.id, queryClient]);
  // Someone answered in another tab or on another device, or a retry raced: refresh to the
  // server's state. The text this tab didn't get to send is kept (below), never cleared.
  useEffect(() => {
    if (error instanceof ApiError && (error.code === "question_not_current" || error.code === "question_answered_elsewhere")) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.interview(iv.id) });
    }
  }, [error, iv.id, queryClient]);
  // The round moved past a question this tab still has unsent text for (answered or skipped
  // elsewhere): show that text, with a way to copy it, until the learner dismisses it.
  const [kept, setKept] = useState<{ index: number; text: string } | null>(null);
  const sendingIndex = useRef<number | null>(null);
  const shownIndex = useRef(index);
  useEffect(() => {
    const previous = shownIndex.current;
    shownIndex.current = index;
    if (previous === index || sendingIndex.current === previous) return;
    const text = readStoredDraft(roundDraftKey(iv.id, previous)).trim();
    if (text) setKept({ index: previous, text });
  }, [index, iv.id]);
  const dismissKept = () => {
    if (kept) clearStoredDraft(roundDraftKey(iv.id, kept.index));
    setKept(null);
  };
  // A new question: move focus to it and, if chosen, have the interviewer read it.
  const prompt = current?.prompt;
  const { autoSpeak } = voice;
  useEffect(() => {
    if (!prompt) return;
    heading.current?.focus();
    if (prefs.readAloud) autoSpeak(prompt);
  }, [prompt, prefs.readAloud, autoSpeak]);

  useRoundViewDiag(iv, pending ? "followup" : current ? "question" : "empty");
  if (!current && !pending) return null; // completed or out of questions; the parent shows results after refetch
  const speaker = pending?.speaker ?? current?.speaker ?? null;

  async function submit(source: AnswerSource): Promise<boolean> {
    const key = roundDraftKey(iv.id, index);
    sendingIndex.current = index;
    try {
      await tracedRoundAction("answer", iv.id, index, (traceparent) =>
        answer.mutateAsync({ question_index: index, answer: draft.trim(), source, traceparent }));
      clearStoredDraft(key);
      return true;
    } catch {
      return false; // the draft is kept (stored) and the error is shown
    } finally {
      sendingIndex.current = null;
    }
  }

  const lowTime = seconds <= 60;
  return (
    <div className="page question-page round">
      <div className="round__bar">
        <p className="eyebrow">{role.toUpperCase()} {format && format.id !== "mixed" ? format.title.toUpperCase() : "INTERVIEW"} · QUESTION {index + 1} OF {iv.questions.length}</p>
        <div className="row">
          <span className={`clock${lowTime ? " clock--low" : ""}`} role="timer" aria-label={`${formatClock(seconds)} remaining`}>
            <Icon name="clock" size={17} />{formatClock(seconds)}
          </span>
          <FocusToggle />
          <Link to="/interviews/questions" className="btn btn--ghost btn--sm">Leave for now</Link>
          <Button size="sm" variant="ghost" disabled={busy}
            onClick={() => {
              if (window.confirm("End the interview for good? Unanswered questions stay unanswered. To come back to it later instead, choose Leave for now: the timer keeps running.")) abandon.mutate();
            }}>
            End early
          </Button>
        </div>
      </div>
      <progress className="round-progress" max={iv.questions.length} value={index} aria-label={`Question ${index + 1} of ${iv.questions.length}`} />
      <p className="subtle round__timer-note">The timer runs on the server and keeps going if you leave this page or your microphone stops. Your typed or spoken draft is saved in this browser. Resume from any tab or device: the first answer the server gets for a question is the one kept.</p>
      {kept && (
        <section className="banner banner--warning stack-sm" role="region" aria-label={`Your unsent answer to question ${kept.index + 1}`}>
          <p>Question {kept.index + 1} already has an answer (sent earlier, or from another tab or device), so this text wasn't sent. It's kept here until you dismiss it.</p>
          <blockquote className="round__kept">{kept.text}</blockquote>
          <div className="row">
            <Button size="sm" variant="secondary" onClick={() => void navigator.clipboard?.writeText(kept.text).catch(() => undefined)}>Copy text</Button>
            <Button size="sm" variant="ghost" onClick={dismissKept}>Dismiss</Button>
          </div>
        </section>
      )}

      <div className="round__layout">
        {pending ? <FollowupTurn iv={iv} followup={pending} voice={voice} readAloud={prefs.readAloud} /> : current && (
        <div className="stack">
          <Card className="question-page__prompt stack">
            {speaker && <p className="eyebrow speaker-eyebrow">{speaker.title.toUpperCase()} ASKS</p>}
            <h1 className="page__title" ref={heading} tabIndex={-1}>{current.title}</h1>
            <p className="row question-page__meta">
              <DifficultyBadge difficulty={current.difficulty as Difficulty} />
              <Badge>{KIND_LABEL[current.kind] ?? titleCase(current.kind)}</Badge>
            </p>
            <p>{current.prompt}</p>
            {voice.supported && (
              <div className="row">
                {voice.speaking
                  ? <Button size="sm" variant="ghost" onClick={voice.stop}><Icon name="stop" size={14} />Stop reading</Button>
                  : <Button size="sm" variant="ghost" onClick={() => voice.speak(current.prompt)}><Icon name="speaker" size={14} />Read question aloud</Button>}
              </div>
            )}
            {prefs.captions && voice.speaking && voice.caption && (
              <p className="voice-caption"><span className="voice-caption__who">{speaker?.title ?? "Interviewer"}:</span> {voice.caption}</p>
            )}
            {speaker && <p className="turn-cue" role="status">Your turn: answer the {speaker.title.toLowerCase()}.</p>}
          </Card>

          <VoiceComposer
            key={index /* a new question (here or from another tab) remounts it: the microphone stops */}
            id="round-answer" label="Your answer" value={draft} onChange={setDraft} onSubmit={submit}
            submitting={answer.isPending} disabled={busy && !answer.isPending} maxLength={6000} onIgnored={() => reportIgnored("answer")}
            submitLabel={index + 1 === iv.questions.length ? "Finish interview" : "Next question"}
            placeholder="Answer the way you'd say it in the interview…" voice={voice}
            hint={`${words(draft)} words · aim for 120-350`} errorId={error ? "round-answer-error" : undefined}
            extraActions={
              <Button type="button" variant="ghost" disabled={busy} loading={skip.isPending}
                onClick={() => void tracedRoundAction("skip", iv.id, index, (traceparent) => skip.mutateAsync({ index, traceparent })).catch(() => undefined)}>Skip</Button>
            }
          />
          {!online && (
            <p className="banner banner--warning" role="status">
              You're offline. Your answer is saved on this device. Send it when you're back online: the interview
              timer keeps running on the server, and nothing is sent automatically.
            </p>
          )}
          <InlineError id="round-answer-error" error={error} />
        </div>
        )}
        <aside className="stack focus-hide">
          {roles.length > 0 && (
            <Card className="stack-sm" role="region" aria-label="Panel">
              <h2 className="section-title">Simulated panel</h2>
              <ul className="panel-roster">
                {roles.map((r) => (
                  <li key={r.id} aria-current={speaker?.id === r.id ? "true" : undefined}>
                    <strong>{r.title}{speaker?.id === r.id ? " · speaking" : ""}</strong>
                    <span className="subtle">{r.objective}</span>
                  </li>
                ))}
              </ul>
              <p className="subtle">Generic roles, not a real employer. One speaks at a time.</p>
            </Card>
          )}
          <EngagementMeter engagement={last} visible={prefs.showEngagement}
            onToggle={() => setPrefs({ showEngagement: !prefs.showEngagement })} />
        </aside>
      </div>
    </div>
  );
}
