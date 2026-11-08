import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";

import {
  queryKeys,
  useAbandonInterview,
  useFinishInterview,
  useInterview,
  useInterviewMessage,
  useProblem,
} from "@/api/queries";
import type { AnswerSource, Interview } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { DifficultyBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { FocusToggle } from "@/features/display/FocusToggle";
import { CodeEditor } from "@/features/workspace/CodeEditor";
import { useDraft } from "@/features/workspace/useDraft";
import { clearStoredDraft, useStoredDraft } from "@/hooks/useStoredDraft";
import { EngagementMeter } from "@/features/voice/EngagementMeter";
import { useInterviewerVoice } from "@/features/voice/useInterviewerVoice";
import { VoiceComposer } from "@/features/voice/VoiceComposer";
import { useVoicePrefs } from "@/features/voice/voicePrefs";

import { PhaseStepper } from "./PhaseStepper";
import { LiveRound } from "./QuestionRound";
import { ReviewWorkspace } from "@/features/review/ReviewWorkspace";
import { Transcript } from "./Transcript";
import { formatClock, useCountdown } from "./useCountdown";
import { Icon } from "@/components/Icon";

export default function InterviewSessionPage() {
  const { id = "" } = useParams();
  const interview = useInterview(id);
  if (interview.isPending) return <LoadingState label="Loading interview…" />;
  if (interview.isError) return <div className="page"><ErrorState error={interview.error} onRetry={() => interview.refetch()} /></div>;
  const iv = interview.data;
  const live = iv.status === "in_progress";
  if (!live) return <ReviewWorkspace iv={iv} />;
  if (iv.kind === "questions") return <LiveRound key={iv.id} iv={iv} />;
  if (!iv.problem) return <div className="page"><ErrorState error={new Error("This interview's problem is no longer available.")} /></div>;
  return <LiveInterview key={iv.id} iv={iv} problemSlug={iv.problem.slug} />;
}

function LiveInterview({ iv, problemSlug }: { iv: Interview; problemSlug: string }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const problem = useProblem(problemSlug);
  const [prefs, setPrefs] = useVoicePrefs();
  const voice = useInterviewerVoice(prefs);
  const draft = useDraft(`interview-${iv.id}`, problem.data?.starter_code ?? "", user?.id ?? "anon");
  const send = useInterviewMessage(iv.id);
  const finish = useFinishInterview(iv.id);
  const abandon = useAbandonInterview(iv.id);
  const messageKey = `codecoach.interview-message.${iv.id}`;
  const [message, setMessage] = useStoredDraft(messageKey);
  // The message being sent, and how many turns the transcript had when it was sent. It is shown
  // only until the transcript grows: the server's copy replaces it in the same render, so the
  // message never appears twice (the cache update and clearing this state are separate steps).
  const [pending, setPending] = useState<{ text: string; baseline: number } | null>(null);
  const pendingText = pending && iv.turns.length === pending.baseline ? pending.text : null;
  // Which candidate turns this tab sent (by position). Any other new one came from another tab or
  // device: the page says so, and the unsent text here stays in the box. The server refuses a
  // message written against an older transcript (409 interview_advanced), so nothing is appended
  // out of context.
  const [mine, setMine] = useState<ReadonlySet<number>>(() => new Set());
  const [seenAtOpen] = useState(iv.turns.length);
  const fromElsewhere = iv.turns.filter((t) => t.role === "candidate" && t.seq >= seenAtOpen && !mine.has(t.seq)).length;
  const markMine = (seq: number, sent: boolean) =>
    setMine((m) => { const next = new Set(m); if (sent) next.add(seq); else next.delete(seq); return next; });
  const [acknowledged, setAcknowledged] = useState(0);
  // A resend of the same text (after a lost response) keeps its request id: the server answers it
  // with what it already did, instead of a second reply.
  const request = useRef<{ text: string; id: string } | null>(null);
  const seconds = useCountdown(iv.deadline_at, true);
  const ready = iv.phase === null; // interviewer wrapped up
  const busy = send.isPending || finish.isPending || abandon.isPending;
  const canSend = !ready && seconds > 0 && iv.candidate_turns_remaining > 0 && !!problem.data && !busy;

  // When the clock runs out, ask the server: it closes the interview and returns feedback.
  useEffect(() => {
    if (seconds === 0) void queryClient.invalidateQueries({ queryKey: queryKeys.interview(iv.id) });
  }, [seconds, iv.id, queryClient]);

  const lastInterviewer = [...iv.turns].reverse().find((t) => t.role === "interviewer");
  const lastEngagement = [...iv.turns].reverse().find((t) => t.role === "candidate" && t.engagement)?.engagement ?? null;
  const { speak } = voice;
  // Read each new interviewer message aloud, if chosen.
  useEffect(() => {
    if (prefs.readAloud && lastInterviewer) speak(lastInterviewer.content);
  }, [lastInterviewer?.seq, prefs.readAloud, speak]); // eslint-disable-line react-hooks/exhaustive-deps

  async function onSend(source: AnswerSource = "typed"): Promise<boolean> {
    const text = message.trim();
    if (!text || !canSend) return false;
    const baseline = iv.turns.length;
    if (request.current?.text !== text) request.current = { text, id: requestId() };
    setPending({ text, baseline });
    setMessage("");
    markMine(baseline, true);
    try {
      await send.mutateAsync({ message: text, code: draft.code, source, after_seq: baseline, client_request_id: request.current.id });
      request.current = null;
      clearStoredDraft(messageKey);
      return true;
    } catch (err) {
      markMine(baseline, false);
      if (err instanceof ApiError && err.code === "network_error") {
        // The server may have taken it before the line dropped: look, rather than send it again.
        const fresh = await queryClient
          .fetchQuery({ queryKey: queryKeys.interview(iv.id), queryFn: () => api.interview(iv.id), staleTime: 0 })
          .catch(() => null);
        const landed = fresh?.turns.find((t) => t.seq === baseline && t.role === "candidate");
        if (landed && landed.content.trim() === text) {
          markMine(baseline, true);
          request.current = null;
          clearStoredDraft(messageKey);
          send.reset();
          return true;
        }
      }
      if (err instanceof ApiError && err.code === "interview_advanced") {
        void queryClient.invalidateQueries({ queryKey: queryKeys.interview(iv.id) }); // show the latest
      }
      setMessage(text); // give the text back (and save it again) so nothing is lost
      return false;
    } finally {
      setPending(null);
    }
  }

  const lowTime = seconds <= 120;
  return (
    <div className="interview">
      <header className="interview__bar">
        <div className="row">
          <h1 className="interview__title">{iv.problem?.title}</h1>
          {iv.problem && <DifficultyBadge difficulty={iv.problem.difficulty} />}
          <Link to={`/problems/${problemSlug}`} target="_blank" rel="noreferrer" className="subtle interview__statement-link">Problem statement <Icon name="arrow" size={14} /><span className="visually-hidden">(opens in a new tab)</span></Link>
        </div>
        <PhaseStepper phaseIndex={iv.phase_index} />
        <div className="row">
          <span className={`clock${lowTime ? " clock--low" : ""}`} role="timer" aria-label={`${formatClock(seconds)} remaining`}>
            <Icon name="clock" size={17} />
            {formatClock(seconds)}
          </span>
          <FocusToggle />
          <Link to="/interviews" className="btn btn--ghost btn--sm">Leave for now</Link>
          <Button size="sm" variant="ghost" loading={abandon.isPending} disabled={busy}
            onClick={() => {
              if (window.confirm("End the interview for good? You'll get feedback on what you've covered so far. To come back to it later instead, choose Leave for now: the timer keeps running.")) abandon.mutate();
            }}>
            End early
          </Button>
          <Button size="sm" variant={ready ? "primary" : "secondary"} loading={finish.isPending} disabled={busy}
            onClick={() => finish.mutate(draft.code)}>
            Finish & get feedback
          </Button>
        </div>
      </header>

      <div className="interview__body">
        <section className="interview__chat" aria-label="Conversation">
          {iv.phase_guide && <p className="interview__guide subtle">Now: {iv.phase_guide}</p>}
          <p className="subtle interview__leave-note">The timer keeps running on the server if you leave. Resume from any tab or device.</p>
          {fromElsewhere > acknowledged && (
            <div className="banner row" role="status">
              <span>Updated from another tab or device: the latest is above. Your unsent text here is still in the box.</span>
              <Button size="sm" variant="ghost" onClick={() => setAcknowledged(fromElsewhere)}>OK</Button>
            </div>
          )}
          <Transcript turns={iv.turns} pending={pendingText} />
          {prefs.captions && voice.speaking && voice.caption && (
            <p className="voice-caption"><span className="voice-caption__who">Interviewer:</span> {voice.caption}</p>
          )}
          <div className="focus-hide display-contents">
            <EngagementMeter engagement={lastEngagement} visible={prefs.showEngagement}
              onToggle={() => setPrefs({ showEngagement: !prefs.showEngagement })} />
          </div>
          <VoiceComposer
            id="iv-message" label="Your answer" value={message} onChange={setMessage} onSubmit={onSend}
            submitting={send.isPending} rows={3} maxLength={4000} submitLabel="Send" voice={voice}
            disabled={ready || seconds === 0 || iv.candidate_turns_remaining === 0 || finish.isPending || abandon.isPending}
            placeholder={ready ? "The interviewer has wrapped up. Click Finish to see your feedback." : "Think out loud… (Ctrl/⌘ + Enter to send)"}
            hint={`${iv.candidate_turns_remaining} messages left`} errorId={send.error ?? finish.error ?? abandon.error ? "iv-error" : undefined}
            extraActions={voice.supported ? (
              <Button type="button" variant="ghost" disabled={!lastInterviewer || voice.speaking}
                onClick={() => lastInterviewer && voice.speak(lastInterviewer.content)}>Replay interviewer</Button>
            ) : undefined}
          />
          <InlineError id="iv-error" error={send.error ?? finish.error ?? abandon.error} />
        </section>
        <section className="interview__code" aria-label="Your code">
          <div className="editor-toolbar">
            <span className="editor-toolbar__lang">Java</span>
            <span className="subtle">Your code is shared with the interviewer when you send a message.</span>
          </div>
          {problem.isError ? <ErrorState error={problem.error} onRetry={() => void problem.refetch()} />
            : problem.data ? <CodeEditor value={draft.code} onChange={draft.setCode} onSubmit={() => void onSend()} />
              : <LoadingState label="Loading editor…" />}
        </section>
      </div>
    </div>
  );
}

function requestId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `msg-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
