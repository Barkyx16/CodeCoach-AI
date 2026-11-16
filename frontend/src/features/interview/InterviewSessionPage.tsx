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
import type { AnswerSource, CoachPreview, FeedbackCheck, Interview } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { DifficultyBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { PrivateUnavailable } from "@/components/Unavailable";
import { isGone } from "@/lib/errors";
import { FocusToggle } from "@/features/display/FocusToggle";
import { CODE_CHANGED, CoachContext } from "@/features/workspace/CoachContext";
import { CodeEditor } from "@/features/workspace/CodeEditor";
import { useDraft } from "@/features/workspace/useDraft";
import { clearStoredDraft, useStoredDraft } from "@/hooks/useStoredDraft";
import { EngagementMeter } from "@/features/voice/EngagementMeter";
import { useInterviewerVoice } from "@/features/voice/useInterviewerVoice";
import { VoiceComposer } from "@/features/voice/VoiceComposer";
import { useVoicePrefs } from "@/features/voice/voicePrefs";

import { INTERVIEWER_REFUSED, SEND_LABEL, feedbackCost, staleness, useCheckEach, type Checked, type Ending } from "./interviewerCheck";
import { PhaseStepper } from "./PhaseStepper";
import { LiveRound } from "./QuestionRound";
import { ReviewWorkspace } from "@/features/review/ReviewWorkspace";
import { InterviewHints } from "./InterviewHints";
import { Transcript } from "./Transcript";
import { formatClock, useCountdown } from "./useCountdown";
import { Icon } from "@/components/Icon";

export default function InterviewSessionPage() {
  const { id = "" } = useParams();
  const interview = useInterview(id);
  if (interview.isPending) return <LoadingState label="Loading interview…" />;
  // Nothing loaded: the error is all there is. Once the interview is on screen, a failed refresh
  // (focus, the clock running out, the check after a dropped send) keeps it there, with a notice.
  if (interview.isError && !interview.data && isGone(interview.error)) {
    return <PrivateUnavailable what="interview" list={{ to: "/history?type=interview", label: "All your interviews" }} />;
  }
  if (interview.isError && !interview.data) {
    return <div className="page"><ErrorState error={interview.error} onRetry={() => interview.refetch()} /></div>;
  }
  const iv = interview.data;
  const stale = interview.isError && (
    <div className="page page--notice">
      <div className="banner banner--warning row" role="status">
        <span>We couldn't check this interview for updates just now. This is how it was last loaded; what you type is kept.</span>
        <Button size="sm" loading={interview.isFetching} onClick={() => void interview.refetch()}>Check again</Button>
      </div>
    </div>
  );
  const live = iv.status === "in_progress";
  if (!live) return <>{stale}<ReviewWorkspace iv={iv} /></>;
  if (iv.kind === "questions") return <>{stale}<LiveRound key={iv.id} iv={iv} /></>;
  if (!iv.problem) return <div className="page"><ErrorState error={new Error("This interview's problem is no longer available.")} /></div>;
  return <>{stale}<LiveInterview key={iv.id} iv={iv} problemSlug={iv.problem.slug} /></>;
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
  // Shortly before time is up (the server's margin: docs/COACH_CONTEXT.md, "What the feedback read"),
  // offer to check what the feedback will read. Once shown it stays until the interview ends.
  const margin = iv.feedback_check_margin_seconds;
  const nearlyUp = margin != null && seconds > 0 && seconds <= margin;
  const canSend = !ready && seconds > 0 && iv.candidate_turns_remaining > 0 && !!problem.data && !busy;

  // When the clock runs out, ask the server: it closes the interview and returns feedback.
  useEffect(() => {
    if (seconds === 0) void queryClient.invalidateQueries({ queryKey: queryKeys.interview(iv.id) });
  }, [seconds, iv.id, queryClient]);

  const lastInterviewer = [...iv.turns].reverse().find((t) => t.role === "interviewer");
  const lastEngagement = [...iv.turns].reverse().find((t) => t.role === "candidate" && t.engagement)?.engagement ?? null;
  const { autoSpeak } = voice;
  // The code editor's Ctrl/⌘+Enter sends through the answer box's own checks (not while the
  // microphone is on, never twice, with the right typed/spoken record).
  const composerSubmit = useRef<(() => void) | null>(null);
  // Read each new interviewer message aloud, if chosen.
  useEffect(() => {
    if (prefs.readAloud && lastInterviewer) autoSpeak(lastInterviewer.content);
  }, [lastInterviewer?.seq, prefs.readAloud, autoSpeak]); // eslint-disable-line react-hooks/exhaustive-deps

  // What the interviewer reads (docs/COACH_CONTEXT.md, "The coding interviewer"): one action away,
  // or before every message and the feedback if the learner chose that (kept on this device). A
  // checked request is sent bound to what was shown; a refusal shows what would be read now.
  const [checkEach, setCheckEach] = useCheckEach();
  const [checked, setChecked] = useState<Checked | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<unknown>(null);
  const [changed, setChanged] = useState<string | null>(null);
  const [cancelled, setCancelled] = useState(false);
  // "I've checked this" (Volume 16, prompt 3): kept with the interview, so a time-out can say so.
  const [confirmedCheck, setConfirmedCheck] = useState<FeedbackCheck | null>(null);
  const [confirming, setConfirming] = useState(false);
  const refusedWith = (err: unknown): CoachPreview | null =>
    err instanceof ApiError && err.code === "context_changed" ? ((err.details as { preview?: CoachPreview } | undefined)?.preview ?? null) : null;

  async function checkMessage(source: AnswerSource = "typed") {
    const text = message.trim();
    if (!text) return;
    setChecking(true);
    setCheckError(null);
    setChanged(null);
    setCancelled(false);
    try {
      const data = await api.interviewMessagePreview(iv.id, { message: text, code: draft.code, after_seq: iv.turns.length });
      setChecked({ kind: "message", data, message: text, code: draft.code, source, turns: iv.turns.length });
    } catch (err) {
      if (err instanceof ApiError && err.code === "interview_advanced") void queryClient.invalidateQueries({ queryKey: queryKeys.interview(iv.id) });
      setCheckError(err);
    } finally {
      setChecking(false);
    }
  }

  async function checkFeedback(ending: Ending) {
    setChecking(true);
    setCheckError(null);
    setChanged(null);
    setCancelled(false);
    try {
      const code = ending === "finished" ? draft.code : null; // ending early reads the code last sent
      const data = await api.interviewFeedbackPreview(iv.id, code === null ? { ending } : { ending, code });
      setChecked({ kind: "feedback", ending, data, code, turns: iv.turns.length });
    } catch (err) {
      setCheckError(err);
    } finally {
      setChecking(false);
    }
  }

  async function confirmChecked() {
    if (!checked || checked.kind !== "feedback") return;
    const { ending, code, data } = checked;
    setConfirming(true);
    setChanged(null);
    try {
      setConfirmedCheck(await api.confirmFeedbackCheck(iv.id, { ending, approved_context: data.context_fingerprint, ...(code === null ? {} : { code }) }));
    } catch (err) {
      const fresh = refusedWith(err);
      if (fresh) {
        // Moved on (another tab sent a message, or the code changed): show what it reads now.
        setChecked({ kind: "feedback", ending, data: fresh, code, turns: iv.turns.length });
        setChanged((err as ApiError).message);
      } else setCheckError(err);
    } finally {
      setConfirming(false);
    }
  }

  async function sendChecked() {
    if (!checked) return;
    const approved = checked.data.context_fingerprint;
    if (checked.kind === "message") {
      const { message: text, code, source } = checked;
      setChecked(null);
      await deliver(text, source, { context: approved, code });
      return;
    }
    const { ending, code } = checked;
    try {
      if (ending === "finished") await finish.mutateAsync({ code, approved_context: approved });
      else await abandon.mutateAsync(approved);
      setChecked(null);
    } catch (err) {
      const fresh = refusedWith(err);
      if (fresh) {
        (ending === "finished" ? finish : abandon).reset(); // the panel says it
        setChecked({ kind: "feedback", ending, data: fresh, code, turns: iv.turns.length });
        setChanged(INTERVIEWER_REFUSED);
      }
    }
  }

  async function onSend(source: AnswerSource = "typed"): Promise<boolean> {
    if (checkEach) {
      // Shown first; the text stays in the box until it's sent from the check.
      if (message.trim() && canSend) void checkMessage(source);
      return false;
    }
    return deliver(message.trim(), source);
  }

  async function deliver(text: string, source: AnswerSource, approved?: { context: string; code: string }): Promise<boolean> {
    if (!text || !canSend) return false;
    const baseline = iv.turns.length;
    if (request.current?.text !== text) request.current = { text, id: requestId() };
    setPending({ text, baseline });
    setMessage("");
    markMine(baseline, true);
    try {
      await send.mutateAsync({
        message: text, code: approved ? approved.code : draft.code, source, after_seq: baseline, client_request_id: request.current.id,
        ...(approved ? { approved_context: approved.context } : {}),
      });
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
      const fresh = refusedWith(err);
      if (fresh && approved) {
        send.reset(); // the check says it, with what would be read now
        setChecked({ kind: "message", data: fresh, message: text, code: approved.code, source, turns: baseline });
        setChanged(INTERVIEWER_REFUSED);
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
              if (!window.confirm("End the interview for good? You'll get feedback on what you've covered so far. To come back to it later instead, choose Leave for now: the timer keeps running.")) return;
              if (checkEach) void checkFeedback("abandoned");
              else abandon.mutate();
            }}>
            End early
          </Button>
          <Button size="sm" variant={ready ? "primary" : "secondary"} loading={finish.isPending} disabled={busy}
            onClick={() => (checkEach ? void checkFeedback("finished") : finish.mutate(draft.code))}>
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
            submitting={send.isPending} rows={3} maxLength={4000} submitLabel="Send" voice={voice} submitRef={composerSubmit}
            disabled={ready || seconds === 0 || iv.candidate_turns_remaining === 0 || finish.isPending || abandon.isPending}
            placeholder={ready ? "The interviewer has wrapped up. Click Finish to see your feedback." : "Think out loud… (Ctrl/⌘ + Enter to send)"}
            hint={`${iv.candidate_turns_remaining} messages left`} errorId={send.error ?? finish.error ?? abandon.error ? "iv-error" : undefined}
            extraActions={voice.supported ? (
              <Button type="button" variant="ghost" disabled={!lastInterviewer || voice.speaking}
                onClick={() => lastInterviewer && voice.speak(lastInterviewer.content)}>Replay interviewer</Button>
            ) : undefined}
          />
          <InlineError id="iv-error" error={send.error ?? finish.error ?? abandon.error} />
          {nearlyUp && (
            // Static text, so it's announced once when it appears, never on the clock's ticks.
            <div className="banner banner--warning row interview__nearly-up" role="status">
              <span>Time is nearly up. When it runs out, the feedback is scored from what you&apos;ve sent so far; checking it doesn&apos;t stop the clock.</span>
              <Button size="sm" variant="secondary" disabled={busy || checking} onClick={() => void checkFeedback("finished")}>Check what the feedback will read</Button>
            </div>
          )}
          <div className="row interview__check">
            <Button size="sm" variant="ghost" loading={checking && checked === null} disabled={!message.trim() || !canSend || checking}
              onClick={() => void checkMessage()}>What the interviewer reads</Button>
            <Button size="sm" variant="ghost" disabled={busy || checking} onClick={() => void checkFeedback("finished")}>What the feedback reads</Button>
            <label className="checkbox">
              <input type="checkbox" checked={checkEach} onChange={(e) => setCheckEach(e.target.checked)} />
              Check every message, and the feedback, before it's sent (kept on this device)
            </label>
          </div>
          <InlineError error={checkError} action="Checking what the interviewer reads" />
          {cancelled && !checked && <p className="subtle" role="status">Cancelled. Nothing was sent.</p>}
          {checked && (
            <CoachContext preview={checked.data} choices={{}} onChoose={() => undefined} title="What the interviewer reads"
              stale={staleness(checked, { message, code: draft.code, turns: iv.turns.length }, CODE_CHANGED)} changed={changed}
              busy={busy || checking} sendLabel={checked.kind === "message" ? SEND_LABEL.message : SEND_LABEL[checked.ending]}
              costNote={checked.kind === "feedback" ? feedbackCost(checked.data.remaining_today) : undefined}
              budgetBlocks={checked.kind === "message"}
              onSend={() => void sendChecked()}
              onCancel={() => { setChecked(null); setChanged(null); setCancelled(true); }}
              onCheckAgain={() => void (checked.kind === "message" ? checkMessage(checked.source) : checkFeedback(checked.ending))} />
          )}
          {checked?.kind === "feedback" && seconds > 0 && (
            <p className="row interview__confirm">
              <Button size="sm" variant="secondary" loading={confirming} disabled={busy || checking || confirming}
                onClick={() => void confirmChecked()}>I&apos;ve checked this</Button>
              <span className="subtle">Keeps this check with the interview. It sends nothing and doesn&apos;t stop the clock.</span>
            </p>
          )}
          {confirmedCheck && (
            // One sentence, the same each time: announced once when it appears.
            <p className="subtle" role="status">{confirmedCheck.text}</p>
          )}
        </section>
        <section className="interview__code" aria-label="Your code">
          <div className="editor-toolbar">
            <span className="editor-toolbar__lang">Java</span>
            <span className="subtle">Your code is shared with the interviewer when you send a message.</span>
          </div>
          {problem.isError ? <ErrorState error={problem.error} onRetry={() => void problem.refetch()} />
            : problem.data ? <CodeEditor value={draft.code} onChange={draft.setCode} onSubmit={() => composerSubmit.current?.()} />
              : <LoadingState label="Loading editor…" />}
          {/* Hints inside the interview (Volume 17, prompt 4): recorded with it, closed once time is up. */}
          {problem.data && problem.data.hint_levels > 0 && (
            <InterviewHints iv={iv} maxLevel={problem.data.hint_levels} open={(iv.seconds_remaining ?? 0) > 0}
              onAsked={() => void queryClient.invalidateQueries({ queryKey: queryKeys.interview(iv.id) })} />
          )}
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
