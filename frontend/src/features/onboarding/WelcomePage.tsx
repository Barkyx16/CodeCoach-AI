import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useCapabilities, useCareers, useOnboarding, useUpdateOnboarding } from "@/api/queries";
import type { OnboardingUpdate } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { CareerSelect } from "@/features/careers/CareerSelect";

import { FeedbackNote } from "./FeedbackNote";

/**
 * The optional first-session choice: one real question (or problem) from the learner's own
 * career, a short tour of that same page, or straight to the library. Nothing here is required;
 * "Not now" goes to the dashboard and Help can bring any of it back.
 */
export function WelcomePage() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const onboarding = useOnboarding();
  const update = useUpdateOnboarding();
  const careers = useCareers();
  const capabilities = useCapabilities().data;
  const execution = capabilities?.execution;
  const retention = capabilities?.guest_retention_days;
  const [changing, setChanging] = useState(false);
  const [track, setTrack] = useState(user?.career_track ?? "");
  const [careerBusy, setCareerBusy] = useState(false);
  const [careerError, setCareerError] = useState<unknown>(null);

  if (onboarding.isPending) return <LoadingState label="Getting things ready…" />;
  if (onboarding.isError) {
    return (
      <div className="page welcome">
        <ErrorState error={onboarding.error} onRetry={() => void onboarding.refetch()} />
        <p className="welcome__fallback"><Link to="/problems">Go to the practice library</Link> · <Link to="/dashboard">Go to your dashboard</Link></p>
      </div>
    );
  }
  const o = onboarding.data;
  const starter = o.starter;
  const careerTitle = careers.data?.find((c) => c.slug === user?.career_track)?.title ?? user?.career_track;

  async function choose(body: OnboardingUpdate, to: string) {
    try {
      await update.mutateAsync(body);
    } catch {
      if (body.tour === "start") return; // the tour needs its saved state; the error is shown below
    }
    navigate(to);
  }

  async function saveCareer() {
    setCareerBusy(true);
    setCareerError(null);
    try {
      setUser(await api.updateProfile({ career_track: track }));
      await qc.invalidateQueries({ queryKey: ["me", "onboarding"] });
      setChanging(false);
    } catch (e) {
      setCareerError(e);
    } finally {
      setCareerBusy(false);
    }
  }

  return (
    <div className="page welcome">
      <div className="page__header">
        <div>
          <p className="eyebrow">WELCOME{user?.is_guest ? " · GUEST SESSION" : ""}</p>
          <h1 className="page__title" tabIndex={-1}>{user?.display_name && !user.is_guest ? `Welcome, ${user.display_name}` : "Welcome to CodeCoach"}</h1>
          <p className="page__subtitle">Choose how to begin. All of it is optional, and you can come back to it from Help.</p>
        </div>
      </div>

      <Card className="stack-sm welcome__career">
        {changing ? (
          <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); void saveCareer(); }}>
            <CareerSelect value={track} onChange={setTrack} required />
            <span className="row">
              <Button type="submit" size="sm" variant="primary" loading={careerBusy} disabled={!track || track === user?.career_track}>Use this job</Button>
              <Button size="sm" variant="ghost" onClick={() => { setTrack(user?.career_track ?? ""); setChanging(false); }}>Cancel</Button>
            </span>
            <InlineError error={careerError} />
          </form>
        ) : (
          <p className="row">
            <span>You're practising for <strong>{careerTitle}</strong>.</span>
            <Button size="sm" variant="ghost" onClick={() => setChanging(true)}>Change job</Button>
          </p>
        )}
      </Card>

      <div className="welcome__choices">
        <Card className="welcome__choice stack-sm">
          <h2 className="section-title">Answer one {starter?.kind === "problem" ? "problem" : "question"} now</h2>
          {starter ? (
            <>
              <p><strong>{starter.title}</strong> <span className="subtle">· {starter.difficulty} · about {starter.minutes} minutes (an estimate)</span></p>
              <FeedbackNote kind={starter.kind} execution={execution} />
              <span><Button variant="primary" loading={update.isPending && update.variables?.start_choice === "practice"}
                onClick={() => void choose({ start_choice: "practice" }, starter.href)}>
                Start this {starter.kind === "problem" ? "problem" : "question"}
              </Button></span>
            </>
          ) : <p className="subtle">There's nothing to start with for this job on this server yet. The library has everything that is available.</p>}
        </Card>

        <Card className="welcome__choice stack-sm">
          <h2 className="section-title">Show me around first</h2>
          <p>A {o.tour_steps}-step tour of the {starter?.kind === "problem" ? "coding workspace" : "question page"}, using that same {starter?.kind === "problem" ? "problem" : "question"}. Leave it whenever you like; it doesn't count as practice.</p>
          {starter && (
            <span><Button variant="secondary" loading={update.isPending && update.variables?.tour === "start"}
              onClick={() => void choose({ start_choice: "intro", tour: "start", tour_kind: o.format }, starter.href)}>
              Start the tour
            </Button></span>
          )}
        </Card>

        <Card className="welcome__choice stack-sm">
          <h2 className="section-title">Browse the library</h2>
          <p>See every {o.format === "coding" ? "problem and question" : "question"} for your job and pick your own.</p>
          <span><Button variant="secondary" onClick={() => void choose({ start_choice: "library" }, "/problems")}>Open the library</Button></span>
        </Card>
      </div>

      <InlineError error={update.error} />
      <p className="welcome__later">
        <Button variant="ghost" onClick={() => void choose({ start_choice: "later" }, "/dashboard")}>Not now, take me to my dashboard</Button>
      </p>
      {user?.is_guest && (
        <p className="subtle">
          This is a guest session{retention ? `: guest accounts are deleted after ${retention} days without activity` : ""}.
          {" "}<Link to="/settings">Create an account</Link> any time to keep your work.
        </p>
      )}
    </div>
  );
}
