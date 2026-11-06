import { useMemo, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useProblems, useQuestion, useResume } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { Icon } from "@/components/Icon";
import { formatClock, useCountdown } from "@/features/interview/useCountdown";
import { timeAgo } from "@/lib/format";

import { findLocalWork } from "./savedWork";

interface Item {
  key: string;
  title: string;
  why: ReactNode;
  to: string;
  action: string;
}

const LAST_STATUS: Record<string, string> = {
  failed: "your last submission didn't pass",
  saved_not_judged: "your last submission was saved but not judged here",
  awaiting_judge: "your last submission is waiting for the judge",
  evaluation_unavailable: "the judge couldn't evaluate your last submission",
};

/**
 * "Continue where you left off", from genuine saved work only, in a fixed priority:
 *   1. an interview in progress (its server timer keeps running and can't pause)
 *   2. an unsent written answer saved in this browser
 *   3. a coding draft saved in this browser
 *   4. the most recent problem you submitted but haven't solved
 *   5. the last question you answered
 * Opening an item never changes the saved work.
 */
export function ContinueCard() {
  const { user } = useAuth();
  const resume = useResume();
  const local = useMemo(() => findLocalWork(user?.id ?? "anon"), [user?.id]);
  const answerQ = useQuestion(local.answerDraft?.track ?? "", local.answerDraft?.questionId ?? "", !!local.answerDraft);
  // The title comes from the library list: fetching the problem itself would record an "open".
  const draftSlug = local.codingDraft?.slug ?? "";
  const codeP = useProblems({ q: draftSlug.replace(/-/g, " "), page_size: 10 }, !!draftSlug);
  const draftTitle = codeP.data?.items.find((p) => p.slug === draftSlug)?.title
    ?? draftSlug.replace(/-/g, " ").replace(/^./, (c) => c.toUpperCase());
  const iv = resume.data?.interview ?? null;
  const seconds = useCountdown(iv?.deadline_at ?? null, !!iv);

  const items: Item[] = [];
  if (iv && seconds > 0) {
    items.push({
      key: "interview", title: iv.title, to: `/interviews/${iv.id}`, action: "Resume interview",
      why: <>In progress with <strong>{formatClock(seconds)}</strong> left. The timer runs on the server, so it kept going while you were away and can't be paused.</>,
    });
  }
  if (local.answerDraft) {
    const { track, questionId, words } = local.answerDraft;
    items.push({
      key: "answer", title: answerQ.data?.title ?? "Your unsent answer", to: `/careers/${track}/questions/${questionId}`, action: "Finish your answer",
      why: <>An unsent answer ({words} {words === 1 ? "word" : "words"}) is saved in this browser.</>,
    });
  }
  if (local.codingDraft) {
    items.push({
      key: "code", title: draftTitle, to: `/problems/${local.codingDraft.slug}`, action: "Open your draft",
      why: <>Your code draft is saved in this browser and opens exactly as you left it.</>,
    });
  }
  const unfinished = resume.data?.unfinished_problem;
  if (unfinished && unfinished.slug !== local.codingDraft?.slug) {
    items.push({
      key: "problem", title: unfinished.title, to: `/problems/${unfinished.slug}`, action: "Keep going",
      why: <>Not solved yet: {LAST_STATUS[unfinished.last_status] ?? "keep working on it"} ({timeAgo(unfinished.at)}).</>,
    });
  }
  const last = resume.data?.last_question;
  if (last && last.question_id !== local.answerDraft?.questionId) {
    items.push({
      key: "question", title: last.title, to: `/careers/${last.track}/questions/${last.question_id}`, action: "Review feedback",
      why: <>Your last answer ({timeAgo(last.at)}). Its feedback and your past answers are saved.</>,
    });
  }

  if (resume.isPending || items.length === 0) return null;
  const [first, ...rest] = items;
  return (
    <section className="card stack continue-card" aria-labelledby="continue-title">
      <h2 className="section-title" id="continue-title"><Icon name="clock" size={16} />Continue where you left off</h2>
      <div className="continue-card__main">
        <div>
          <strong className="continue-card__title">{first!.title}</strong>
          <p className="subtle">{first!.why}</p>
        </div>
        <Link to={first!.to} className="btn btn--primary btn--md">{first!.action} <Icon name="arrow" size={15} /></Link>
      </div>
      {rest.length > 0 && (
        <details className="continue-card__more">
          <summary>Also saved ({rest.length})</summary>
          <ul className="rec-list">
            {rest.slice(0, 3).map((i) => (
              <li key={i.key}><Link to={i.to} className="rec"><strong>{i.title}</strong><span className="subtle">{i.why}</span></Link></li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
