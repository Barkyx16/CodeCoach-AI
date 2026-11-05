import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { queryKeys, useAnswerQuestion, useBookmarks, useCapabilities, useCareers, useContentMeta, useMyAnswers, useQuestion } from "@/api/queries";
import type { Capabilities, Difficulty, InterviewAnswer } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Badge, DifficultyBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Icon } from "@/components/Icon";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";
import { answerDraftKey } from "@/features/dashboard/savedWork";
import { FocusToggle } from "@/features/display/FocusToggle";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { useOnline } from "@/hooks/useOnline";
import { useStoredDraft } from "@/hooks/useStoredDraft";
import { SaveOffline } from "@/features/offline/SaveOffline";
import { ContentInfo } from "@/features/content/ContentInfo";
import { ReportIssue } from "@/features/content/ReportIssue";
import { timeAgo } from "@/lib/format";

import { LearnLinks } from "@/features/learn/LearnLinks";
import { NoteCapture } from "@/features/notes/NoteCapture";
import { QueueBar } from "@/features/saved/QueueBar";
import { SaveControls } from "@/features/saved/SaveControls";
import { ShareEntry } from "@/features/sharing/ShareEntry";

import { GuidedTour } from "@/features/onboarding/GuidedTour";
import { StoryPicker } from "@/features/stories/StoryPicker";
import { ScheduleLink } from "@/features/schedule/ScheduleLink";

import { AnswerRecap } from "./AnswerRecap";
import { AnswerReviewPanel } from "./AnswerReviewPanel";
import { CriteriaPanel } from "./CriteriaPanel";
import { FeedbackCard } from "./FeedbackCard";
import { SelfReviewGate } from "./SelfReviewGate";
import { KIND_LABEL } from "./kinds";
import { keyFor, sendSignature, type PendingSend } from "./sendKey";
import { previousTry, tryNumbers } from "./tries";

const MAX_CHARS = 6000;
const REFLECT_KEY = "codecoach.reflect-first";

function countWords(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

/** A question link that leads nowhere: say so, and lead back to that career's questions. */
function QuestionUnavailable({ track }: { track: string }) {
  const { user } = useAuth();
  const careers = useCareers();
  const career = careers.data?.find((c) => c.slug === track);
  const to = career && user?.career_track !== track ? `/problems?career=${track}&view=questions` : "/problems?view=questions";
  return (
    <div className="page">
      <EmptyState pageTitle title="This question isn't available"
        action={<Link className="btn btn--primary btn--md" to={to}>{career ? `Browse ${career.title} questions` : "Browse interview questions"}</Link>}>
        <p>The link may be mistyped, or the question may have been removed from the library.</p>
      </EmptyState>
    </div>
  );
}

/** One interview question: read it, write an answer, get rubric feedback, compare with past tries. */
/**
 * One page per question: moving to another question starts it afresh, so the previous one's
 * feedback (shown, or still on its way) never appears there. The page that sent an answer owns its
 * feedback; if the learner moves on first, the answer is still saved and listed under its own
 * question and in History. (Leaving doesn't stop the server grading it.)
 */
export function QuestionPage() {
  const { track = "", id = "" } = useParams();
  return <QuestionPageFor key={`${track}/${id}`} />;
}

function QuestionPageFor() {
  const { track = "", id = "" } = useParams();
  const { isAuthenticated, isRestoring, user, continueAsGuest, draftScope, offlineUser } = useAuth();
  const online = useOnline();
  const question = useQuestion(track, id, !isRestoring); // its best score depends on who's asking
  const answers = useMyAnswers(track, id, isAuthenticated);
  const submit = useAnswerQuestion(track, id);
  // This server keeps at most one saved answer per send key (an older one would ignore the key,
  // so none is sent and no protection is claimed).
  const keyed = useCapabilities().data?.answer_request_keys === true;
  const queryClient = useQueryClient();
  const pendingSend = useRef<PendingSend | null>(null);
  const content = useContentMeta("question", `${track}/${id}`);
  const bookmarks = useBookmarks(isAuthenticated);
  const retired = content.data?.status === "retired";
  // Unsent drafts are kept in this browser; a draft carried over from an interview that ended
  // before this question was answered fills an empty box (never overwrites one).
  const location = useLocation();
  const carried = (location.state as { draft?: string } | null)?.draft ?? "";
  const [draft, setDraft, kept] = useStoredDraft(answerDraftKey(draftScope, track, id));
  useLeaveWarning(!kept && draft.trim().length > 0);
  useEffect(() => {
    if (carried && !draft) setDraft(carried);
  }, [carried]); // eslint-disable-line react-hooks/exhaustive-deps
  // ?answer=<id> opens that past answer's feedback (from History, or chosen under "Your past
  // answers"); without it, the answer sent from this page is shown. Each keeps its own identity.
  const [params, setParams] = useSearchParams();
  const wanted = params.get("answer");
  const [sent, setSent] = useState<InterviewAnswer | null>(null);
  const selected = wanted ? answers.data?.find((a) => a.id === wanted) ?? (sent?.id === wanted ? sent : null) : null;
  const shown = wanted ? selected : sent;
  const isNew = !!shown && shown.id === sent?.id;
  // A revision aimed at one missing point: the box starts from the earlier answer (only if it's
  // empty), and sending saves a new try; the earlier one is never changed.
  const [revising, setRevising] = useState<{ fromId: string; target: { label: string; advice: string } | null; keptText: boolean } | null>(null);
  const [cleared, setCleared] = useState<string | null>(null);
  // Sending failed without a reply, and the answer isn't among the saved ones (yet).
  // No reply came back: "keyed" only when the server said again, just now, that it keeps one answer
  // per key (it may have been replaced since the page loaded); otherwise no protection is claimed.
  const [unconfirmed, setUnconfirmed] = useState<null | "keyed" | "plain">(null);
  const [guestError, setGuestError] = useState<unknown>(null);
  const [storyId, setStoryId] = useState<string | null>(null);
  // Optional: reflect on the answer before the coach's feedback is shown (remembered on this device).
  const [reflectFirst, setReflectFirst] = useState(() => {
    try { return localStorage.getItem(REFLECT_KEY) === "on"; } catch { return false; }
  });
  const [gated, setGated] = useState(false);
  const [reflected, setReflected] = useState<string | null>(null);
  // After sending, the emptied box disables "Get feedback", and browsers drop focus from a disabled
  // button: move it to what just appeared (the feedback, or the reflection step before it), so
  // keyboard and screen-reader users land on the result instead of the top of the page.
  const focusResult = useRef(false);
  useEffect(() => {
    if (!focusResult.current || !sent) return;
    focusResult.current = false;
    document.getElementById(gated ? "self-review-title" : "feedback-title")?.focus();
  }, [sent, gated]);

  if (question.isPending) return <LoadingState label="Loading question…" />;
  if (question.isError) {
    // Not there (mistyped, or removed from the library): a retry can't help, a way back can.
    if (question.error instanceof ApiError && question.error.status === 404) return <QuestionUnavailable track={track} />;
    return <div className="page"><ErrorState error={question.error} onRetry={() => question.refetch()} /></div>;
  }
  const q = question.data;
  const savedVersion = bookmarks.data?.find((b) => b.item_type === "question" && b.track === track && b.ref_id === id)?.content_version ?? null;
  const words = countWords(draft);
  const backTo = user?.career_track === track ? "/problems?view=questions" : `/problems?career=${track}&view=questions`;
  // The list this question was opened from (its filters, level and search are in its URL), kept
  // across "Next question"; only the library's own paths, never anything else from history state.
  const navState = location.state as { from?: string; listFrom?: string } | null;
  const listTo = [navState?.listFrom, navState?.from].find((path): path is string => !!path && /^\/problems(\?|$)/.test(path)) ?? backTo;
  const numbers = answers.data ? tryNumbers(answers.data) : null;
  const tryOf = (a: InterviewAnswer | null) => (a && numbers?.get(a.id)) ?? null;
  // Compare with the try this one explicitly revises when it's listed, else with the one before it.
  const parent = shown?.revises_answer_id ? answers.data?.find((a) => a.id === shown.revises_answer_id) ?? null : null;
  const previous = parent ?? (shown && answers.data ? previousTry(answers.data, shown) : null);
  const rubrics = new Set(answers.data?.map((a) => a.rubric_version));
  const revisingFrom = revising ? answers.data?.find((a) => a.id === revising.fromId) ?? (sent?.id === revising.fromId ? sent : null) : null;
  const fromLabel = revisingFrom && tryOf(revisingFrom) ? `try ${tryOf(revisingFrom)}` : "your earlier answer";
  const canRevise = (isAuthenticated || !!offlineUser) && online && !retired;

  /** Show one past answer: in the URL, so a reload or Back keeps it (the page's own state stays). */
  function choose(answerId: string) {
    setParams((p) => { p.set("answer", answerId); return p; }, { replace: true, state: location.state });
  }

  function revise(target: { label: string; advice: string } | null) {
    if (!shown) return;
    const keptText = !!draft.trim() && draft.trim() !== shown.answer.trim();
    if (!draft.trim()) setDraft(shown.answer);
    setCleared(null);
    setRevising({ fromId: shown.id, target, keptText });
    window.setTimeout(() => {
      const box = document.getElementById("answer-text") as HTMLTextAreaElement | null;
      box?.focus();
      box?.setSelectionRange(box.value.length, box.value.length);
    }, 0);
  }

  /** Ask the server once (a read, no retry) whether it still keeps one answer per key. */
  async function stillKeyed(): Promise<"keyed" | "plain"> {
    const now = await api.capabilities().catch(() => null);
    if (now) queryClient.setQueryData<Capabilities>(queryKeys.capabilities, now);
    return now?.answer_request_keys === true ? "keyed" : "plain";
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    const known = new Set(answers.data?.map((a) => a.id));
    // An explicit revision says which try it revises; anything else is a new try.
    const revisesAnswerId = revising?.fromId ?? null;
    // The same send resent (no reply, a failure) keeps its key; a changed or new send gets a new one.
    const send = keyed
      ? keyFor(pendingSend.current, sendSignature({ account: user?.id ?? "", track, questionId: id, answer: text, storyId, revisesAnswerId }))
      : null;
    pendingSend.current = send;
    setUnconfirmed(null);
    let failure: unknown = null;
    let result = await submit.mutateAsync({ answer: text, storyId, requestKey: send?.key ?? null, revisesAnswerId })
      .catch((err: unknown) => { failure = err; return null; });
    // No reply at all (a dropped connection): the server may still have saved it. Look at the saved
    // answers before suggesting a resend that would save it twice.
    if (!result && isAuthenticated && failure instanceof ApiError && failure.status === 0) {
      const fresh = await answers.refetch().catch(() => null);
      const saved = fresh?.data?.find((a) => !known.has(a.id) && a.answer.trim() === text) ?? null;
      if (saved) {
        submit.reset();
        result = saved;
      } else {
        setUnconfirmed(send ? await stillKeyed() : "plain");
      }
    }
    if (result) {
      pendingSend.current = null; // saved: the next send is a new try with a new key
      focusResult.current = true;
      setSent(result);
      if (wanted) setParams((p) => { p.delete("answer"); return p; }, { replace: true, state: location.state });
      setGated(reflectFirst); // the answer is saved either way; only the reveal waits
      setDraft("");
      setRevising(null);
      setCleared(null);
      setStoryId(null); // the next answer is only tied to a story if you choose one again
    }
  }

  return (
    <div className="page question-page">
      <div className="focus-hide display-contents">
        <BackLink />
        {isAuthenticated && <QueueBar item={{ item_type: "question", track, ref_id: id }} />}
        <nav className="question-page__crumbs" aria-label="Breadcrumb">
          <Link to={listTo}><Icon name="book" size={15} />{q.career_title} questions</Link>
        </nav>
      </div>
      <div className="page__header">
        <div>
          <p className="eyebrow">{(KIND_LABEL[q.kind] ?? q.kind).toUpperCase()} QUESTION</p>
          <h1 className="page__title">{q.title}</h1>
          <p className="row question-page__meta">
            <DifficultyBadge difficulty={q.difficulty as Difficulty} />
            <Badge>{KIND_LABEL[q.kind] ?? q.kind}</Badge>
            {q.best_scored != null && <span className="focus-hide"><Badge tone="success">Best score {q.best_scored}</Badge></span>}
            {q.best_scored == null && q.score_status === "too_short" && <span className="focus-hide"><Badge>Answered, too short to score</Badge></span>}
          </p>
        </div>
        <FocusToggle />
      </div>

      <div className="question-page__layout">
        <div className="stack">
          <ContentInfo type="question" id={`${track}/${id}`}
            seenVersion={answers.data?.[0]?.content_version ?? savedVersion}
            seenWhat={answers.data?.[0] ? "answered" : "saved"} />
          <Card className="question-page__prompt" data-tour="question">
            <h2 className="visually-hidden">The question</h2>
            <p>{q.prompt}</p>
          </Card>
          {content.data && <div className="focus-hide"><ReportIssue type="question" id={`${track}/${id}`} version={content.data.version} excerptSource={draft.trim() || undefined} /></div>}

          <div className="focus-hide"><CriteriaPanel track={track} questionId={id} /></div>

          <form className="card stack" onSubmit={onSubmit} aria-labelledby="answer-title">
            <h2 className="section-title" id="answer-title">Write your answer</h2>
            {revising && (
              <div className="banner banner--info revise-note">
                <p>
                  <strong>{revising.target ? `Revising ${fromLabel}: add “${revising.target.label}”.` : `Adding to ${fromLabel}.`}</strong>
                  {revising.target && <> {revising.target.advice}</>}
                </p>
                <p className="subtle">
                  {revising.keptText
                    ? "Your unsent text is still in the box; it wasn't replaced with the earlier answer. "
                    : "The box starts from your earlier answer. Sending saves a new try; the earlier one stays as it was. "}
                  Describe only what really happened: if you don't remember a detail, leave it out rather than add one.
                </p>
                <span className="row">
                  {draft.trim() && <Button size="sm" variant="ghost" onClick={() => {
                    setCleared(draft);
                    setDraft("");
                    document.getElementById("answer-text")?.focus();
                  }}>Start from a blank box</Button>}
                  <Button size="sm" variant="ghost" onClick={() => setRevising(null)}>Hide this note</Button>
                </span>
              </div>
            )}
            {cleared !== null && (
              <p className="row subtle" role="status">
                The box is empty now.
                <Button size="sm" variant="ghost" onClick={() => { setDraft(cleared); setCleared(null); }}>Undo</Button>
              </p>
            )}
            {isAuthenticated && <div className="focus-hide"><StoryPicker track={track} questionId={id} draft={draft} setDraft={setDraft} storyId={storyId} setStoryId={setStoryId} /></div>}
            <label className="visually-hidden" htmlFor="answer-text">Your answer</label>
            <textarea id="answer-text" data-tour="answer" className="input answer-input" rows={10} maxLength={MAX_CHARS} value={draft}
              placeholder="Write it the way you'd say it in the interview…"
              aria-describedby={submit.error ? "answer-count answer-error" : "answer-count"}
              aria-invalid={submit.error instanceof ApiError && submit.error.status === 422 ? true : undefined}
              onChange={(e) => { setDraft(e.target.value); setCleared(null); }} />
            <div className="answer-actions">
              <span id="answer-count" className="subtle" data-tour="draft">{words} {words === 1 ? "word" : "words"} · aim for 120-350</span>
              {isAuthenticated || offlineUser ? (
                <Button type="submit" variant="primary" data-tour="feedback" loading={submit.isPending} disabled={!draft.trim() || !online || retired}
                  aria-describedby={!online ? "answer-offline" : retired ? "answer-retired" : undefined}>
                  Get feedback
                </Button>
              ) : (
                <span className="row" data-tour="feedback">
                  <Link className="btn btn--secondary btn--md" to="/login" state={{ from: `/careers/${track}/questions/${id}` }}>Sign in</Link>
                  <Button variant="primary" onClick={() => { setGuestError(null); continueAsGuest(undefined, track).catch(setGuestError); }}>
                    Try as a guest
                  </Button>
                </span>
              )}
            </div>
            {draft.trim() && (kept
              ? <p className="subtle draft-state">Draft saved on this device, not sent yet.</p>
              : <p className="banner banner--warning" role="alert">Your draft couldn't be saved on this device (browser storage is blocked or full). Copy it somewhere safe before leaving this page.</p>)}
            {(isAuthenticated || offlineUser) && (
              <label className="checkbox focus-hide">
                <input type="checkbox" checked={reflectFirst} onChange={(e) => {
                  setReflectFirst(e.target.checked);
                  try { localStorage.setItem(REFLECT_KEY, e.target.checked ? "on" : "off"); } catch { /* this visit only */ }
                }} />
                Reflect on my answer before seeing the feedback (optional)
              </label>
            )}
            {retired && <p className="subtle" id="answer-retired">This question is retired, so it isn't graded any more. Your draft stays on this device.</p>}
            {!online && <p className="subtle" id="answer-offline">You're offline. Feedback needs a connection; your draft stays on this device until you send it.</p>}
            {!isAuthenticated && !offlineUser && <p className="subtle">Feedback needs an account so your answers are saved. A guest session takes one click.</p>}
            <InlineError id="answer-error" error={submit.error ?? guestError} />
            {unconfirmed && (
              <p className="banner banner--warning" role="status">
                No reply came back, so it isn't certain whether this answer was saved, and it isn't among your saved answers
                yet. Your text is still here. {unconfirmed === "keyed"
                  ? "Sending it again unchanged is safe: if the first one did arrive, you'll get that answer back instead of a second copy."
                  : "When you're connected, look under “Your past answers” before sending it again."}
              </p>
            )}
          </form>

          {shown && gated && isNew ? (
            <SelfReviewGate answer={shown} onDone={() => { focusResult.current = true; setGated(false); setReflected(shown.id); }} />
          ) : shown && (
            <>
              <div data-tour="next">
                <FeedbackCard answer={shown} track={track} draft={draft}
                  title={isNew ? "Feedback" : `Feedback on ${tryOf(shown) ? `try ${tryOf(shown)}` : "your answer"} from ${timeAgo(shown.created_at)}`} />
              </div>
              <AnswerRecap answer={shown} tryNo={tryOf(shown)} previous={previous} previousNo={tryOf(previous)} previousIsParent={!!parent}
                track={track} questionId={id} difficulty={q.difficulty as Difficulty} backTo={listTo}
                canRevise={canRevise} onRevise={revise} />
              {isAuthenticated && <div className="focus-hide"><AnswerReviewPanel key={shown.id} answerId={shown.id} defaultOpen={reflected === shown.id} /></div>}
            </>
          )}
          {shown && isAuthenticated && !(gated && isNew) && <div className="focus-hide"><ShareEntry answerId={shown.id} fromLabel="Back to the question" /></div>}
          {wanted && answers.data && !selected && <p className="banner banner--warning">That answer couldn't be found. It may have been deleted.</p>}
        </div>

        <aside className="stack">
          <div className="focus-hide display-contents">
            <LearnLinks query={{ track, question_id: id }} from={{ from: `/careers/${track}/questions/${id}`, fromLabel: "Back to the question" }} />
            {isAuthenticated && <SaveControls item={{ item_type: "question", track, ref_id: id }} title={q.title} />}
            {isAuthenticated && <p className="schedule-link-row"><ScheduleLink kind="question" refId={`${track}/${id}`} title={q.title} /></p>}
            {isAuthenticated && <NoteCapture source={{ type: "question", id, track }} excerpt={q.prompt} excerptLabel="the question" />}
          </div>
          <div className="focus-hide display-contents"><SaveOffline kind="question" itemKey={`${track}/${id}`} label="question" /></div>
          <Card className="stack">
            <h2 className="section-title"><Icon name="spark" size={16} />Tips</h2>
            <ul className="mini-list">{q.tips.map((t) => <li key={t}>{t}</li>)}</ul>
          </Card>
          {isAuthenticated && answers.data && answers.data.length > 0 && (
            <Card className="stack focus-hide">
              <h2 className="section-title">Your past answers</h2>
              {!numbers && <p className="subtle">Your {answers.data.length} most recent answers to this question.</p>}
              <ul className="past-answers">
                {answers.data.map((a) => (
                  <li key={a.id}>
                    <button type="button" className="past-answers__item" onClick={() => choose(a.id)}
                      aria-pressed={shown?.id === a.id}>
                      <span>{numbers?.get(a.id) ? `Try ${numbers.get(a.id)}${numbers.get(a.id) === 1 ? " (first)" : ""}` : timeAgo(a.created_at)}</span>
                      <span className="subtle">
                        {a.evidence_level === "insufficient" ? "Too short to score" : a.evidence_level === "unknown" ? `${a.score}/100, not counted (how it was graded wasn't recorded)` : `${a.score}/100 · ${a.rating}`}
                        {numbers ? ` · ${timeAgo(a.created_at)}` : ""}
                        {rubrics.size > 1 ? ` · rubric ${a.rubric_version}` : ""}
                        {a.revises_answer_id ? ` · revised from ${numbers?.get(a.revises_answer_id) ? `try ${numbers.get(a.revises_answer_id)}` : "an earlier answer"}` : ""}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              {rubrics.size > 1 && <p className="subtle">These were graded with different rubric versions, so their scores aren't directly comparable.</p>}
            </Card>
          )}
        </aside>
      </div>
      <GuidedTour kind="written" />
    </div>
  );
}
