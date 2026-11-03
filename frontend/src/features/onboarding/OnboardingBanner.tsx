import { Link, useNavigate } from "react-router-dom";

import { useOnboarding, useUpdateOnboarding } from "@/api/queries";
import type { OnboardingUpdate } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";

const FORMAT_TEXT = {
  written: "Practice for this job is written answers to interview questions, with feedback from the built-in rubric coach.",
  coding: "Practice for this job includes coding problems checked by the server's judge, plus written interview questions.",
} as const;

/**
 * At most one onboarding message on the dashboard, and each can be dismissed for good: the
 * welcome for someone who hasn't started yet, a way back into a tour they left, or a short
 * introduction after switching to a career with a different kind of practice.
 */
export function OnboardingBanner() {
  const { isAuthenticated } = useAuth();
  const state = useOnboarding(isAuthenticated);
  const update = useUpdateOnboarding();
  const navigate = useNavigate();
  const o = state.data;
  if (!o) return null;

  const act = async (body: OnboardingUpdate, to?: string) => {
    try {
      await update.mutateAsync(body);
      if (to) navigate(to);
    } catch {
      /* shown below */
    }
  };
  const tourMatchesStarter = o.starter && ((o.starter.kind === "problem") === (o.tour_kind === "coding"));

  let content = null;
  if (o.welcome_due) {
    content = (
      <>
        <div><strong>New here?</strong> <span>Start with one {o.format === "coding" ? "problem" : "question"} from your job, or take a short tour first.</span></div>
        <span className="row">
          <Link className="btn btn--primary btn--sm" to="/welcome">Get started</Link>
          <Button size="sm" variant="ghost" onClick={() => void act({ dismiss: "welcome" })}>Dismiss</Button>
        </span>
      </>
    );
  } else if (o.resume_due) {
    content = (
      <>
        <div><strong>You left the introduction at step {o.tour_step + 1} of {o.tour_steps}.</strong> <span>Pick it up where you left off, or dismiss this; Help can restart it.</span></div>
        <span className="row">
          {o.starter && (tourMatchesStarter
            ? <Button size="sm" variant="primary" onClick={() => void act({ tour: "step", tour_step: o.tour_step }, o.starter!.href)}>Resume</Button>
            : <Button size="sm" variant="primary" onClick={() => void act({ tour: "start", tour_kind: o.format }, o.starter!.href)}>Start it for this job</Button>)}
          <Button size="sm" variant="ghost" onClick={() => void act({ dismiss: "resume_tour" })}>Dismiss</Button>
        </span>
      </>
    );
  } else if (o.career_intro) {
    const intro = o.career_intro;
    content = (
      <>
        <div><strong>You're now practising for {intro.title}.</strong> <span>{FORMAT_TEXT[intro.kind]} Your earlier practice is kept.</span></div>
        <span className="row">
          {o.starter && <Button size="sm" variant="primary" onClick={() => void act({ career_intro_seen: true, tour: "start", tour_kind: intro.kind }, o.starter!.href)}>Take the {o.tour_steps}-step tour</Button>}
          <Button size="sm" variant="ghost" onClick={() => void act({ career_intro_seen: true })}>Not now</Button>
        </span>
      </>
    );
  }
  if (!content) return null;
  return (
    <section className="onboarding-banner" aria-label="Getting started">
      {content}
      <InlineError error={update.error} />
    </section>
  );
}
