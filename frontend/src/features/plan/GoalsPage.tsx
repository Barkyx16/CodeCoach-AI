import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useGoals, useSaveGoals } from "@/api/queries";
import type { Goals, GoalsInput } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { useCameFrom } from "@/hooks/useCameFrom";

const EXPERIENCE = [
  { id: "new", label: "New to the field", hint: "Starting with easy questions" },
  { id: "early", label: "Early career (0-2 years)", hint: "Easy questions first" },
  { id: "mid", label: "Experienced (3-7 years)", hint: "Medium questions" },
  { id: "senior", label: "Senior (8+ years)", hint: "Hard questions" },
] as const;
const WEEKLY = [30, 60, 90, 120, 180];
const MAX_FOCUS = 8;
type Format = NonNullable<GoalsInput["formats"]>[number];
const FORMATS: Format[] = ["written", "voice", "coding"];

/** Optional goal setup. Everything can be left blank; saving never resets progress. */
export function GoalsPage() {
  const goals = useGoals();
  if (goals.isPending) return <LoadingState label="Loading your goals…" />;
  if (goals.isError) return <div className="page"><ErrorState error={goals.error} onRetry={() => void goals.refetch()} /></div>;
  return <GoalsForm key={goals.data.track} goals={goals.data} />;
}

function GoalsForm({ goals }: { goals: Goals }) {
  const navigate = useNavigate();
  const came = useCameFrom();
  const returnTo = came?.from ?? "/dashboard";
  const save = useSaveGoals();
  const [form, setForm] = useState<GoalsInput>({
    track: goals.track, specialty: goals.specialty ?? "", experience: goals.experience ?? null,
    target_date: goals.target_date ?? null, weekly_minutes: goals.weekly_minutes ?? null,
    focus_areas: goals.focus_areas ?? [], formats: goals.formats?.length ? goals.formats : ["written", ...(goals.has_coding ? ["coding" as const] : [])],
    confidence: goals.confidence, setup_skipped: false,
  });
  const set = (patch: Partial<GoalsInput>) => setForm((f) => ({ ...f, ...patch }));
  const toggle = <T,>(list: T[], value: T) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  const focus = form.focus_areas ?? [];

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const body: GoalsInput = {
      ...form, specialty: form.specialty?.trim() || null,
      confidence: Object.fromEntries(Object.entries(form.confidence ?? {}).filter(([k]) => focus.includes(k))),
    };
    try {
      await save.mutateAsync(body);
      // Back where the goals were opened from (the plan, or the dashboard by default), not always
      // the dashboard. Replace: Back from there shouldn't reopen the saved form.
      navigate(returnTo, { replace: Boolean(came) });
    } catch {
      /* shown below */
    }
  }

  return (
    <div className="page goals-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">YOUR PLAN · {goals.career_title.toUpperCase()}</p>
          <h1 className="page__title">Your goals</h1>
          <p className="page__subtitle">All optional. Your plan uses what you share; changing it later keeps everything you've practised.</p>
        </div>
      </div>
      <form className="stack" onSubmit={onSubmit} aria-label="Your goals">
        <Card className="stack">
          <p className="subtle">Career: <strong>{goals.career_title}</strong> (<Link to="/settings#account">change in Settings</Link>)</p>
          <label className="field">
            <span className="field__label">Specialty or focus (optional)</span>
            <input className="input" maxLength={120} value={form.specialty ?? ""} placeholder="e.g. Emergency department, Backend APIs"
              onChange={(e) => set({ specialty: e.target.value })} />
          </label>
          <fieldset className="field">
            <legend className="field__label">Experience</legend>
            <div className="choice-grid">
              {EXPERIENCE.map((x) => (
                <label key={x.id} className={`choice${form.experience === x.id ? " choice--active" : ""}`}>
                  <input type="radio" name="experience" checked={form.experience === x.id} onChange={() => set({ experience: x.id })} />
                  <span><strong>{x.label}</strong><span className="subtle">{x.hint}</span></span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="goals-page__row">
            <label className="field">
              <span className="field__label">Interview date (if you know it)</span>
              <input className="input" type="date" value={form.target_date ?? ""} onChange={(e) => set({ target_date: e.target.value || null })} />
            </label>
            <label className="field">
              <span className="field__label">Practice time per week</span>
              <select className="select" value={form.weekly_minutes ?? ""} onChange={(e) => set({ weekly_minutes: e.target.value ? Number(e.target.value) : null })}>
                <option value="">Not sure (plan for 60 minutes)</option>
                {WEEKLY.map((m) => <option key={m} value={m}>{m >= 60 ? `${m / 60} hour${m > 60 ? "s" : ""}` : `${m} minutes`}</option>)}
              </select>
            </label>
          </div>
          <fieldset className="field">
            <legend className="field__label">How you want to practise</legend>
            <div className="row">
              {FORMATS.filter((f) => f !== "coding" || goals.has_coding).map((f) => (
                <label key={f} className="checkbox">
                  <input type="checkbox" checked={(form.formats ?? []).includes(f)} onChange={() => set({ formats: toggle(form.formats ?? [], f) })} />
                  {f === "written" ? "Written answers" : f === "voice" ? "Speaking out loud" : "Coding problems"}
                </label>
              ))}
            </div>
          </fieldset>
        </Card>
        <Card className="stack">
          <fieldset className="field">
            <legend className="field__label">Where do you want help? (up to {MAX_FOCUS})</legend>
            <div className="skill-grid">
              {goals.skills.map((s) => {
                const on = focus.includes(s);
                return (
                  <label key={s} className={`checkbox${on ? " checkbox--on" : ""}`}>
                    <input type="checkbox" checked={on} disabled={!on && focus.length >= MAX_FOCUS}
                      onChange={() => set({ focus_areas: toggle(focus, s) })} />
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </label>
                );
              })}
            </div>
          </fieldset>
          {focus.length > 0 && (
            <fieldset className="field">
              <legend className="field__label">How confident do you feel? (optional, 1 = not yet, 5 = very)</legend>
              <p className="subtle">This is kept separate from your scores. It's never mixed into them.</p>
              {focus.map((s) => (
                <label key={s} className="confidence-row">
                  <span>{s}</span>
                  <select className="select" value={form.confidence?.[s] ?? ""} onChange={(e) => {
                    const next = { ...(form.confidence ?? {}) };
                    if (e.target.value) next[s] = Number(e.target.value);
                    else delete next[s];
                    set({ confidence: next });
                  }}>
                    <option value="">Prefer not to say</option>
                    {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </label>
              ))}
            </fieldset>
          )}
        </Card>
        <InlineError error={save.error} />
        <div className="row">
          <Button type="submit" variant="primary" loading={save.isPending}>Save goals</Button>
          <Link to={returnTo} className="btn btn--ghost btn--md">Cancel</Link>
        </div>
      </form>
    </div>
  );
}
