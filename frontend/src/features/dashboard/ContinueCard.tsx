import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useProblems, useQuestion, useRecentWork, useResume } from "@/api/queries";
import type { RecentItem, RequestOutcome } from "@/api/types";
import { countLocalWork } from "@/auth/localWork";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { formatClock, useCountdown } from "@/features/interview/useCountdown";
import { timeAgo } from "@/lib/format";
import { forgetIntent, listIntents, type IntentKind, type PendingIntent } from "@/lib/pendingIntents";
import { storage } from "@/lib/storage";

import { findLocalWork } from "./savedWork";

/**
 * "Continue your work" (Volume 11, prompt 1; docs/CONTINUE.md): a small starting view, in four
 * groups that never pretend to be each other:
 *   1. an interview in progress (its server timer keeps running and can't pause);
 *   2. records saved to the account, newest first, with the time each really keeps (saved,
 *      started, finished; never "opened", which isn't recorded);
 *   3. drafts only in this browser, labelled so;
 *   4. actions sent before a reload whose reply never came, with a read-only "Check result".
 * Loading it only reads: nothing is sent, started or graded. One source failing leaves the others.
 */

export const CONTINUE_HIDDEN_KEY = "codecoach.continue.hidden";

const LAST_STATUS: Record<string, string> = {
  failed: "your last submission didn't pass",
  saved_not_judged: "your last submission was saved but not judged here",
  awaiting_judge: "your last submission is waiting for the judge",
  evaluation_unavailable: "the judge couldn't evaluate your last submission",
};

const TYPE_LABEL: Record<RecentItem["type"], string> = {
  interview: "Interview", note: "Note", story: "Story", kit: "Interview-day kit",
  application: "Application", offer_comparison: "Offer comparison",
};
const STATE_LABEL: Record<NonNullable<RecentItem["state"]>, string> = {
  in_progress: "in progress", time_up: "time's up", finished: "finished", expired: "time ran out", ended_early: "ended early",
};

function pathOf(i: RecentItem): string {
  const id = encodeURIComponent(i.id);
  switch (i.type) {
    case "interview": return `/interviews/${id}`;
    case "note": return `/notes/${id}`;
    case "story": return `/stories/${id}`;
    case "kit": return `/applications/${encodeURIComponent(i.parent_id ?? "")}/events/${id}/kit`;
    case "application": return `/applications/${id}`;
    case "offer_comparison": return `/offers/compare/${id}`;
  }
}

function actionOf(i: RecentItem): string {
  if (i.type !== "interview") return "Open";
  return i.state === "in_progress" ? "Resume" : "See results";
}

const INTENT_LABEL: Record<IntentKind, string> = {
  submission: "Code submission", run: "Code run", hint: "Hint request", review: "Code review request",
  story: "Story save", note_copy: "Note copy",
};

/** Where what an earlier request made can be seen. */
function outcomeLink(o: RequestOutcome): { to: string; label: string } | null {
  if (o.problem_slug && ["submission", "run", "hint", "review", "explain"].includes(o.kind)) {
    return { to: `/problems/${encodeURIComponent(o.problem_slug)}`, label: "Open the problem" };
  }
  if (o.kind === "story") return { to: `/stories/${encodeURIComponent(o.id)}`, label: "Open the story" };
  if (o.kind === "note") return { to: `/notes/${encodeURIComponent(o.id)}`, label: "Open the note" };
  return null;
}

type Check = { status: "checking" } | { status: "found"; outcome: RequestOutcome } | { status: "not_found" }
  | { status: "in_progress" } | { status: "unavailable" };

/** One earlier action: asked about only when the learner presses Check result, never sent again. */
function PendingRow({ userId, intent }: { userId: string; intent: PendingIntent }) {
  const [check, setCheck] = useState<Check | null>(null);
  async function run() {
    setCheck({ status: "checking" });
    try {
      const outcome = await api.requestOutcome(intent.key); // a read: what this key made, if anything
      forgetIntent(userId, intent.kind, intent.target, intent.key);
      setCheck({ status: "found", outcome });
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        forgetIntent(userId, intent.kind, intent.target, intent.key);
        setCheck({ status: "not_found" });
      } else if (e instanceof ApiError && e.code === "request_in_progress") {
        setCheck({ status: "in_progress" });
      } else {
        setCheck({ status: "unavailable" });
      }
    }
  }
  const sent = new Date(intent.sentAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const link = check?.status === "found" ? outcomeLink(check.outcome) : null;
  return (
    <li className="continue-item">
      <div>
        <strong>{INTENT_LABEL[intent.kind]}</strong>
        <span className="subtle"> · sent at {sent}, reply never came</span>
        <p className="subtle" role="status">
          {check?.status === "checking" && "Checking…"}
          {check?.status === "found" && <>It arrived{check.outcome.state === "pending" ? " and is still being judged" : ""}. {link && <Link to={link.to}>{link.label}</Link>}</>}
          {check?.status === "not_found" && "It never arrived, so nothing was made. Sending it now would be a new one."}
          {check?.status === "in_progress" && "It's still being answered. Check again in a moment."}
          {check?.status === "unavailable" && "Couldn't check just now. Nothing was sent again; try once more."}
        </p>
      </div>
      {(check === null || check.status === "in_progress" || check.status === "unavailable") && (
        <Button size="sm" variant="secondary" onClick={() => void run()}>{check ? "Check again" : "Check result"}</Button>
      )}
    </li>
  );
}

export function ContinueCard() {
  const { user } = useAuth();
  const userId = user?.id ?? "anon";
  const [hidden, setHidden] = useState(() => storage.get(CONTINUE_HIDDEN_KEY) === "1");
  const resume = useResume(!hidden);
  const recent = useRecentWork(!hidden);
  const local = useMemo(() => findLocalWork(userId), [userId]);
  const answerQ = useQuestion(local.answerDraft?.track ?? "", local.answerDraft?.questionId ?? "", !!local.answerDraft && !hidden);
  // The title comes from the library list: fetching the problem itself would record an "open".
  const draftSlug = local.codingDraft?.slug ?? "";
  const codeP = useProblems({ q: draftSlug.replace(/-/g, " "), page_size: 10 }, !!draftSlug && !hidden);
  const draftTitle = codeP.data?.items.find((p) => p.slug === draftSlug)?.title
    ?? draftSlug.replace(/-/g, " ").replace(/^./, (c) => c.toUpperCase());
  const [intents] = useState(() => (user ? listIntents(user.id) : []));
  const otherCopies = useMemo(() => Math.max(0, countLocalWork(userId) - (local.answerDraft ? 1 : 0) - (local.codingDraft ? 1 : 0)), [userId, local]);
  const iv = resume.data?.interview ?? null;
  const seconds = useCountdown(iv?.deadline_at ?? null, !!iv && !hidden);

  const setHiddenPref = (on: boolean) => {
    setHidden(on);
    if (on) storage.set(CONTINUE_HIDDEN_KEY, "1");
    else storage.remove(CONTINUE_HIDDEN_KEY);
  };
  if (hidden) {
    return (
      <p className="continue-hidden subtle">
        Continue your work is hidden. <Button size="sm" variant="ghost" onClick={() => setHiddenPref(false)}>Show it</Button>
      </p>
    );
  }

  const live = iv && seconds > 0 ? iv : null;
  const saved = (recent.data?.items ?? []).filter((i) => !(live && i.type === "interview" && i.id === live.id));
  const unfinished = resume.data?.unfinished_problem;
  const showUnfinished = unfinished && unfinished.slug !== local.codingDraft?.slug;
  const last = resume.data?.last_question;
  const showLast = last && last.question_id !== local.answerDraft?.questionId;
  const deviceCount = (local.answerDraft ? 1 : 0) + (local.codingDraft ? 1 : 0);
  const loading = recent.isPending && resume.isPending;
  const nothing = !loading && !live && saved.length === 0 && !showUnfinished && !showLast && deviceCount === 0
    && otherCopies === 0 && intents.length === 0 && !recent.isError && !resume.isError;

  return (
    <section className="card stack continue-card" aria-labelledby="continue-title">
      <div className="continue-card__head">
        <h2 className="section-title" id="continue-title"><Icon name="clock" size={16} />Continue your work</h2>
        <Button size="sm" variant="ghost" onClick={() => setHiddenPref(true)}>Hide</Button>
      </div>
      {loading && <p className="subtle" role="status">Loading your recent work…</p>}
      {nothing && (
        <p className="subtle">
          Nothing to continue yet. Interviews in progress, work you save, and drafts kept in this browser will show up here.
        </p>
      )}

      {live && (
        <div className="continue-card__main">
          <div>
            <strong className="continue-card__title">{live.title}</strong>
            <p className="subtle">In progress with <strong>{formatClock(seconds)}</strong> left. The timer runs on the server, so it kept going while you were away and can't be paused.</p>
          </div>
          <Link to={`/interviews/${live.id}`} className="btn btn--primary btn--md">Resume interview <Icon name="arrow" size={15} /></Link>
        </div>
      )}

      {(saved.length > 0 || showUnfinished || showLast || recent.isError || resume.isError || (recent.data?.unavailable.length ?? 0) > 0) && (
        <div className="stack-sm" role="group" aria-labelledby="continue-saved">
          <h3 className="review-minor" id="continue-saved">Saved to your account</h3>
          {recent.isError && (
            <p className="banner banner--warning">
              Your recent saved work couldn't be loaded just now. The rest of this section still works.{" "}
              <Button size="sm" variant="ghost" onClick={() => void recent.refetch()}>Try again</Button>
            </p>
          )}
          {(recent.data?.unavailable.length ?? 0) > 0 && (
            <p className="subtle">Your {recent.data!.unavailable.join(" and ")} couldn't be loaded just now; everything else is listed.</p>
          )}
          {resume.isError && <p className="subtle">Your last problem and question couldn't be loaded just now.</p>}
          <ul className="rec-list">
            {saved.map((i) => (
              <li key={`${i.type}:${i.id}`}>
                <Link to={pathOf(i)} className="rec">
                  <strong>{i.title}</strong>
                  <span className="subtle">
                    {TYPE_LABEL[i.type]}{i.state ? ` · ${STATE_LABEL[i.state]}` : ""}{i.detail ? ` · ${i.detail}` : ""} · {i.at_meaning} {timeAgo(i.at)} · {actionOf(i)}
                  </span>
                </Link>
              </li>
            ))}
            {showUnfinished && (
              <li>
                <Link to={`/problems/${unfinished.slug}`} className="rec">
                  <strong>{unfinished.title}</strong>
                  <span className="subtle">Coding problem · not solved yet: {LAST_STATUS[unfinished.last_status] ?? "keep working on it"} ({timeAgo(unfinished.at)}) · Keep going</span>
                </Link>
              </li>
            )}
            {showLast && (
              <li>
                <Link to={`/careers/${last.track}/questions/${last.question_id}`} className="rec">
                  <strong>{last.title}</strong>
                  <span className="subtle">Your last answer ({timeAgo(last.at)}); its feedback and your past answers are saved · Review feedback</span>
                </Link>
              </li>
            )}
          </ul>
        </div>
      )}

      {(deviceCount > 0 || otherCopies > 0) && (
        <div className="stack-sm" role="group" aria-labelledby="continue-device">
          <h3 className="review-minor" id="continue-device">Only in this browser</h3>
          <p className="subtle">Not on your account yet, and not on your other devices.</p>
          <ul className="rec-list">
            {local.answerDraft && (
              <li>
                <Link to={`/careers/${local.answerDraft.track}/questions/${local.answerDraft.questionId}`} className="rec">
                  <strong>{answerQ.data?.title ?? "Your unsent answer"}</strong>
                  <span className="subtle">An unsent answer ({local.answerDraft.words} {local.answerDraft.words === 1 ? "word" : "words"}) · Finish your answer</span>
                </Link>
              </li>
            )}
            {local.codingDraft && (
              <li>
                <Link to={`/problems/${local.codingDraft.slug}`} className="rec">
                  <strong>{draftTitle}</strong>
                  <span className="subtle">Code you haven't submitted, opens exactly as you left it · Open your draft</span>
                </Link>
              </li>
            )}
          </ul>
          {otherCopies > 0 && (
            <p className="subtle">{otherCopies} more {otherCopies === 1 ? "copy" : "copies"} in this browser. <Link to="/settings/data">See them in Your data</Link></p>
          )}
        </div>
      )}

      {user && intents.length > 0 && (
        <div className="stack-sm" role="group" aria-labelledby="continue-waiting">
          <h3 className="review-minor" id="continue-waiting">Waiting for a reply</h3>
          <p className="subtle">Sent before a reload and never answered. Checking only asks what happened; nothing is sent again.</p>
          <ul className="continue-list">
            {intents.slice(0, 3).map((i) => <PendingRow key={i.key} userId={user.id} intent={i} />)}
          </ul>
        </div>
      )}
    </section>
  );
}
