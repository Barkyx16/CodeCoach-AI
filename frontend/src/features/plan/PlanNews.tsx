import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { useUpdatePlan } from "@/api/queries";
import type { Plan, PlanNews as News } from "@/api/types";
import { Button } from "@/components/Button";
import { describeError } from "@/lib/errors";

interface Notice { version: number; text: string }

const KIND = { answer: "Answer", retry: "Retry", round: "Round", submission: "Submission" } as const;
const label = (e: News["entries"][number]) => (e.exercise ? "Debugging exercise" : KIND[e.kind]);

/**
 * Practice this plan version doesn't use yet that would change it (docs/PLAN_UPDATES.md): one line
 * and one button. Nothing updates by itself; "Update my plan" asks for the next version from the
 * version shown here, and if another tab or device updated first, says so and shows that one.
 */
export function PlanNews({ plan, minutes, compact = false }: { plan: Plan; minutes: number; compact?: boolean }) {
  const update = useUpdatePlan(minutes);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const id = useId();
  const news = plan.news;
  const shown = notice && notice.version === plan.version ? notice : null;

  const press = () => {
    const seen = plan.version;
    setFailed(null);
    update.mutate({ version: seen, track: plan.track }, {
      onSuccess: (next) => setNotice(next.version === seen
        ? { version: seen, text: "Nothing to update: what's new no longer changes your plan." }
        : { version: next.version, text: `Your plan is now version ${next.version}. What changed is listed with it.` }),
      onError: (err) => {
        const current = err instanceof ApiError && err.code === "plan_changed"
          ? (err.details as { version?: number | null } | null)?.version ?? null : null;
        if (current) setNotice({ version: current, text: `Your plan was already updated, in another tab or on another device: this is version ${current}.` });
        else setFailed(describeError(err).message);
      },
    });
  };

  return (
    <>
      {shown && <UpdatedNotice text={shown.text} />}
      {news && (
        <section className="plan-news" aria-labelledby={id}>
          <p className="plan-news__line" id={id}>
            <strong>{news.text}</strong> Your plan stays as it is until you update it.
          </p>
          {!compact && (news.by_skill ?? []).length > 0 && (
            // What each skill's new evidence would move in the next version, one sentence each (Volume 16, prompt 7).
            <ul className="mini-list plan-news__skills" aria-label="What it would change, by skill">
              {(news.by_skill ?? []).map((g) => <li key={g.text}>{g.text}</li>)}
            </ul>
          )}
          {!compact && news.rule && <p className="subtle">{news.rule}</p>}
          {!compact && (
            <details className="plan-news__details">
              <summary>What's new ({news.entries.length})</summary>
              <ul className="mini-list">
                {news.entries.map((e) => (
                  <li key={e.href}>
                    <Link to={e.href}>{label(e)}: {e.title}</Link>
                    {e.score !== null && e.score !== undefined && <span className="subtle"> · {e.score}/100</span>}
                    {e.verdict && <span className="subtle"> · {e.verdict_detail ?? e.verdict}</span>}
                  </li>
                ))}
              </ul>
              {(news.not_counted ?? []).map((line) => <p key={line} className="subtle">{line}</p>)}
            </details>
          )}
          <Button size="sm" variant="secondary" loading={update.isPending} onClick={press}>Update my plan</Button>
          {failed && <p className="banner banner--danger" role="alert">{failed} Your plan wasn't changed.</p>}
        </section>
      )}
    </>
  );
}

/** Where focus goes once the button is gone: the result, said once. */
function UpdatedNotice({ text }: { text: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  useEffect(() => ref.current?.focus(), [text]);
  return <p className="plan-news__notice" role="status" tabIndex={-1} ref={ref}>{text}</p>;
}
