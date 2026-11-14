import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useGoals, useSaveGoals } from "@/api/queries";
import type { Goals, GoalsInput } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { useCameFrom } from "@/hooks/useCameFrom";
import { allowLeaveAfterSave, useLeaveWarning } from "@/hooks/useLeaveWarning";
import { formDraftKey, useFormDraft } from "@/hooks/useFormDraft";
import { useAuth } from "@/auth/useAuth";
import { FormDraftOffer, FormDraftStatus } from "@/components/FormDraftNotice";
import { ErrorSummary, ControlField, FieldError } from "@/components/FieldErrors";
import { invalidProps, useFieldErrors } from "@/hooks/useFieldErrors";

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
/** What a refused save can name, in the form's order, with where each one is (Volume 9, prompt 3). */
const GOAL_FIELDS = ["specialty", "experience", "target_date", "weekly_minutes", "formats", "focus_areas", "confidence"] as const;
type GoalField = (typeof GOAL_FIELDS)[number];
const GOAL_LABELS: Record<GoalField, string> = {
  specialty: "Specialty or focus", experience: "Experience", target_date: "Interview date", weekly_minutes: "Practice time per week",
  formats: "How you want to practise", focus_areas: "Where you want help", confidence: "How confident you feel",
};
const goalId = (k: GoalField) => `goals-${k.replace(/_/g, "-")}`;
const goalErrorId = (k: GoalField) => `${goalId(k)}-error`;

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
  // Unsaved: the form differs from what was loaded or last saved (typing and putting it back
  // isn't a change). Leaving then asks first (Volume 9, prompt 1).
  const [accepted, setAccepted] = useState(() => JSON.stringify(form));
  const [savedMore, setSavedMore] = useState(false);
  const current = useRef(form);
  useEffect(() => { current.current = form; }, [form]);
  const dirty = JSON.stringify(form) !== accepted;
  useLeaveWarning(dirty, "your goals");
  // A copy kept in this browser while unsaved, offered back after a reload (Volume 9, prompt 2).
  const { user } = useAuth();
  const draft = useFormDraft<GoalsInput>({
    storageKey: formDraftKey(user?.id ?? "anon", "goals", goals.track), form, baseline: JSON.parse(accepted) as GoalsInput,
    base: null, isForm: isGoalsForm, enabled: Boolean(user),
  });
  // A refused save: each error beside its field while that field holds the refused value, and a
  // summary that takes focus (Volume 9, prompt 3).
  const fieldErrors = useFieldErrors(GOAL_FIELDS, form, { ids: goalId, summaryId: "goals-errors" });
  const err = (k: GoalField) => fieldErrors.errorFor(k);
  const set = (patch: Partial<GoalsInput>) => setForm((f) => ({ ...f, ...patch }));
  const toggle = <T,>(list: T[], value: T) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  const focus = form.focus_areas ?? [];

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const body: GoalsInput = {
      ...form, specialty: form.specialty?.trim() || null,
      confidence: Object.fromEntries(Object.entries(form.confidence ?? {}).filter(([k]) => focus.includes(k))),
    };
    const sent = JSON.stringify(form);
    const sentForm = form;
    fieldErrors.clear();
    try {
      await save.mutateAsync(body);
      setAccepted(sent);
      draft.accepted(JSON.parse(sent) as GoalsInput, current.current);
      if (JSON.stringify(current.current) !== sent) {
        // Changed while saving: what was sent is saved; the newer choices stay, still unsaved.
        setSavedMore(true);
        return;
      }
      // Back where the goals were opened from (the plan, or the dashboard by default), not always
      // the dashboard. Replace: Back from there shouldn't reopen the saved form. This one move is
      // what the save allows; later edits ask again.
      allowLeaveAfterSave();
      navigate(returnTo, { replace: Boolean(came) });
    } catch (error) {
      fieldErrors.rejected(error, sentForm); // a validation error goes beside its fields; anything else is shown below
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
      {draft.offer && (
        <FormDraftOffer what="your goals" at={draft.offer.at} onDiscard={draft.discard}
          onRestore={() => { const d = draft.restore(); if (d) setForm({ ...d.form, track: goals.track }); }} />
      )}
      <form className="stack" onSubmit={onSubmit} aria-label="Your goals">
        <ErrorSummary id="goals-errors" other={fieldErrors.other}
          items={fieldErrors.active.map(({ name, message }) => ({ fieldId: goalId(name), label: GOAL_LABELS[name], message }))} />
        <Card className="stack">
          <p className="subtle">Career: <strong>{goals.career_title}</strong> (<Link to="/settings#account">change in Settings</Link>)</p>
          <ControlField id={goalId("specialty")} label="Specialty or focus (optional)" error={err("specialty")}>
            <input className="input" id={goalId("specialty")} maxLength={120} value={form.specialty ?? ""} placeholder="e.g. Emergency department, Backend APIs"
              onChange={(e) => set({ specialty: e.target.value })} {...invalidProps(goalErrorId("specialty"), err("specialty"))} />
          </ControlField>
          <fieldset className="field" id={goalId("experience")} aria-describedby={err("experience") ? goalErrorId("experience") : undefined}>
            <legend className="field__label">Experience</legend>
            <FieldError id={goalErrorId("experience")} message={err("experience")} />
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
            <ControlField id={goalId("target_date")} label="Interview date (if you know it)" error={err("target_date")}>
              <input className="input" id={goalId("target_date")} type="date" value={form.target_date ?? ""} onChange={(e) => set({ target_date: e.target.value || null })}
                {...invalidProps(goalErrorId("target_date"), err("target_date"))} />
            </ControlField>
            <ControlField id={goalId("weekly_minutes")} label="Practice time per week" error={err("weekly_minutes")}>
              <select className="select" id={goalId("weekly_minutes")} value={form.weekly_minutes ?? ""} onChange={(e) => set({ weekly_minutes: e.target.value ? Number(e.target.value) : null })}
                {...invalidProps(goalErrorId("weekly_minutes"), err("weekly_minutes"))}>
                <option value="">Not sure (plan for 60 minutes)</option>
                {WEEKLY.map((m) => <option key={m} value={m}>{m >= 60 ? `${m / 60} hour${m > 60 ? "s" : ""}` : `${m} minutes`}</option>)}
              </select>
            </ControlField>
          </div>
          <fieldset className="field" id={goalId("formats")} aria-describedby={err("formats") ? goalErrorId("formats") : undefined}>
            <legend className="field__label">How you want to practise</legend>
            <FieldError id={goalErrorId("formats")} message={err("formats")} />
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
          <fieldset className="field" id={goalId("focus_areas")} aria-describedby={err("focus_areas") ? goalErrorId("focus_areas") : undefined}>
            <legend className="field__label">Where do you want help? (up to {MAX_FOCUS})</legend>
            <FieldError id={goalErrorId("focus_areas")} message={err("focus_areas")} />
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
            <fieldset className="field" id={goalId("confidence")} aria-describedby={err("confidence") ? goalErrorId("confidence") : undefined}>
              <legend className="field__label">How confident do you feel? (optional, 1 = not yet, 5 = very)</legend>
              <FieldError id={goalErrorId("confidence")} message={err("confidence")} />
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
        {!fieldErrors.shown && <InlineError error={save.error} />}
        <FormDraftStatus changed={dirty} kept={draft.kept} competing={draft.competing}
          copyText={() => [form.specialty, ...(form.focus_areas ?? [])].filter(Boolean).join("\n")} />
        {savedMore && dirty && <p className="subtle" role="status">Saved what you had when you pressed Save. You changed more since: save again to keep those changes.</p>}
        <div className="row">
          <Button type="submit" variant="primary" loading={save.isPending}>Save goals</Button>
          <Link to={returnTo} className="btn btn--ghost btn--md">Cancel</Link>
        </div>
      </form>
    </div>
  );
}

/** A stored goals copy is usable only if it still has the form's shape. */
function isGoalsForm(v: unknown): v is GoalsInput {
  if (!v || typeof v !== "object") return false;
  const f = v as Record<string, unknown>;
  return typeof f.track === "string" && (f.focus_areas === undefined || Array.isArray(f.focus_areas))
    && (f.formats === undefined || Array.isArray(f.formats));
}
