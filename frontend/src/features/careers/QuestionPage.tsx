import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { useAnswerQuestion, useBookmarks, useContentMeta, useMyAnswers, useQuestion } from "@/api/queries";
import type { Difficulty, InterviewAnswer } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Badge, DifficultyBadge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Icon } from "@/components/Icon";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
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

import { AnswerReviewPanel } from "./AnswerReviewPanel";
import { CriteriaPanel } from "./CriteriaPanel";
import { FeedbackCard } from "./FeedbackCard";
import { SelfReviewGate } from "./SelfReviewGate";
import { KIND_LABEL } from "./kinds";

const MAX_CHARS = 6000;
const REFLECT_KEY = "codecoach.reflect-first";

function countWords(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

/** One interview question: read it, write an answer, get rubric feedback, compare with past tries. */
export function QuestionPage() {
  const { track = "", id = "" } = useParams();
  const { isAuthenticated, isRestoring, user, continueAsGuest, draftScope, offlineUser } = useAuth();
  const online = useOnline();
  const question = useQuestion(track, id, !isRestoring); // its best score depends on who's asking
  const answers = useMyAnswers(track, id, isAuthenticated);
  const submit = useAnswerQuestion(track, id);
  const content = useContentMeta("question", `${track}/${id}`);
  const bookmarks = useBookmarks(isAuthenticated);
  const retired = content.data?.status === "retired";
  // Unsent drafts are kept in this browser; a draft carried over from an interview that ended
  // before this question was answered fills an empty box (never overwrites one).
  const carried = (useLocation().state as { draft?: string } | null)?.draft ?? "";
  const [draft, setDraft, kept] = useStoredDraft(answerDraftKey(draftScope, track, id));
  useLeaveWarning(!kept && draft.trim().length > 0);
  useEffect(() => {
    if (carried && !draft) setDraft(carried);
  }, [carried]); // eslint-disable-line react-hooks/exhaustive-deps
  // ?answer=<id> (from History) opens that past answer's feedback.
  const [params] = useSearchParams();
  const wanted = params.get("answer");
  const [latest, setLatest] = useState<InterviewAnswer | null>(null);
  const linked = wanted && answers.data ? answers.data.find((a) => a.id === wanted) ?? null : null;
  const shown = latest ?? linked;
  const [guestError, setGuestError] = useState<unknown>(null);
  const [storyId, setStoryId] = useState<string | null>(null);
  // Optional: reflect on the answer before the coach's feedback is shown (remembered on this device).
  const [reflectFirst, setReflectFirst] = useState(() => {
    try { return localStorage.getItem(REFLECT_KEY) === "on"; } catch { return false; }
  });
  const [gated, setGated] = useState(false);
  const [reflected, setReflected] = useState<string | null>(null);

  if (question.isPending) return <LoadingState label="Loading question…" />;
  if (question.isError) {
    return <div className="page"><ErrorState error={question.error} onRetry={() => question.refetch()} /></div>;
  }
  const q = question.data;
  const savedVersion = bookmarks.data?.find((b) => b.item_type === "question" && b.track === track && b.ref_id === id)?.content_version ?? null;
  const words = countWords(draft);
  const backTo = user?.career_track === track ? "/problems?view=questions" : `/problems?career=${track}&view=questions`;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const result = await submit.mutateAsync({ answer: draft.trim(), storyId }).catch(() => null);
    if (result) {
      setLatest(result);
      setGated(reflectFirst); // the answer is saved either way; only the reveal waits
      setDraft("");
      setStoryId(null); // the next answer is only tied to a story if you choose one again
    }
  }

  return (
    <div className="page question-page">
      <div className="focus-hide display-contents">
        <BackLink />
        {isAuthenticated && <QueueBar item={{ item_type: "question", track, ref_id: id }} />}
        <nav className="question-page__crumbs" aria-label="Breadcrumb">
          <Link to={backTo}><Icon name="book" size={15} />{q.career_title} questions</Link>
        </nav>
      </div>
      <div className="page__header">
        <div>
          <p className="eyebrow">{(KIND_LABEL[q.kind] ?? q.kind).toUpperCase()} QUESTION</p>
          <h1 className="page__title">{q.title}</h1>
          <p className="row question-page__meta">
            <DifficultyBadge difficulty={q.difficulty as Difficulty} />
            <Badge>{KIND_LABEL[q.kind] ?? q.kind}</Badge>
            {q.best_score !== null && q.best_score !== undefined && <span className="focus-hide"><Badge tone="success">Best score {q.best_score}</Badge></span>}
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
            {isAuthenticated && <div className="focus-hide"><StoryPicker track={track} questionId={id} draft={draft} setDraft={setDraft} storyId={storyId} setStoryId={setStoryId} /></div>}
            <label className="visually-hidden" htmlFor="answer-text">Your answer</label>
            <textarea id="answer-text" data-tour="answer" className="input answer-input" rows={10} maxLength={MAX_CHARS} value={draft}
              placeholder="Write it the way you'd say it in the interview…"
              aria-describedby={submit.error ? "answer-count answer-error" : "answer-count"}
              aria-invalid={submit.error instanceof ApiError && submit.error.status === 422 ? true : undefined}
              onChange={(e) => setDraft(e.target.value)} />
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
          </form>

          {shown && gated && shown === latest ? (
            <SelfReviewGate answer={shown} onDone={() => { setGated(false); setReflected(shown.id); }} />
          ) : shown && (
            <>
              <div data-tour="next"><FeedbackCard answer={shown} track={track} title={shown === latest ? "Feedback" : `Feedback on your answer from ${timeAgo(shown.created_at)}`} /></div>
              {isAuthenticated && <div className="focus-hide"><AnswerReviewPanel key={shown.id} answerId={shown.id} defaultOpen={reflected === shown.id} /></div>}
            </>
          )}
          {shown && isAuthenticated && !(gated && shown === latest) && <div className="focus-hide"><ShareEntry answerId={shown.id} fromLabel="Back to the question" /></div>}
          {wanted && answers.data && !linked && !latest && <p className="banner banner--warning">That answer couldn't be found. It may have been deleted.</p>}
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
              <ul className="past-answers">
                {answers.data.map((a) => (
                  <li key={a.id}>
                    <button type="button" className="past-answers__item" onClick={() => setLatest(a)}
                      aria-pressed={shown?.id === a.id}>
                      <span>{a.rating}</span>
                      <span className="subtle">{a.score}/100 · {timeAgo(a.created_at)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </aside>
      </div>
      <GuidedTour kind="written" />
    </div>
  );
}
