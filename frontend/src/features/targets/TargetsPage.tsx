import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useTargetMutation, useTargets } from "@/api/queries";
import type { TargetSummary } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";
import { CareerSelect } from "@/features/careers/CareerSelect";
import { DEFAULT_TRACK } from "@/features/careers/practiceTrack";
import { FormDraftOffer, FormDraftStatus } from "@/components/FormDraftNotice";
import { formDraftKey, isTextForm, useFormDraft } from "@/hooks/useFormDraft";
import { allowLeaveAfterSave, useLeaveWarning } from "@/hooks/useLeaveWarning";

const MAX_DESCRIPTION = 20_000;

/** Saved target roles and a form to add one from a pasted job description. */
export function TargetsPage() {
  const targets = useTargets();
  const [adding, setAdding] = useState(false);
  const list = targets.data ?? [];
  const active = list.filter((t) => !t.archived);
  const archived = list.filter((t) => t.archived);
  return (
    <div className="page targets-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">PREPARE FOR A ROLE</p>
          <h1 className="page__title">Target roles</h1>
          <p className="page__subtitle">Paste a job description to see what it asks for, how much you've practised each part, and what to do next.</p>
        </div>
        {!adding && <Button variant="primary" onClick={() => setAdding(true)}>Add a target role</Button>}
      </div>
      {adding && <NewTarget onCancel={() => setAdding(false)} />}
      {targets.isPending ? <LoadingState /> : targets.isError ? <ErrorState error={targets.error} onRetry={() => void targets.refetch()} />
        : list.length === 0 && !adding ? (
          <EmptyState title="No target roles yet" action={<Button variant="primary" onClick={() => setAdding(true)}>Add a target role</Button>}>
            Paste the text of a job posting. CodeCoach finds the requirements, maps them to practice and shows your coverage.
          </EmptyState>
        ) : (
          <>
            {active.length > 0 && <ul className="target-list">{active.map((t) => <TargetRow key={t.id} t={t} />)}</ul>}
            {archived.length > 0 && (
              <details className="target-archived">
                <summary>Archived ({archived.length})</summary>
                <ul className="target-list">{archived.map((t) => <TargetRow key={t.id} t={t} />)}</ul>
              </details>
            )}
          </>
        )}
    </div>
  );
}

function TargetRow({ t }: { t: TargetSummary }) {
  return (
    <li>
      <Link to={`/targets/${t.id}`} className="activity-row">
        <span className="activity-row__main">
          <span className="row activity-row__title">
            {t.selected && <Badge tone="success">Active</Badge>}
            {t.archived && <Badge>Archived</Badge>}
            <strong>{t.title}</strong>
          </span>
          <span className="subtle activity-row__meta">
            {[t.employer, t.career_title, t.interview_date ? `Interview ${t.interview_date}` : null].filter(Boolean).join(" · ")}
          </span>
        </span>
        <span className="activity-row__side subtle">
          <span>{t.requirements} requirements</span>
          <span>{t.gaps} {t.gaps === 1 ? "gap" : "gaps"} in the bank</span>
        </span>
      </Link>
    </li>
  );
}

function NewTarget({ onCancel }: { onCancel: () => void }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const create = useTargetMutation(api.createTarget);
  const [empty] = useState(() => ({
    title: "", employer: "", description: "", track: user?.career_track || DEFAULT_TRACK, interview_date: "", notes: "",
  }));
  const [form, setForm] = useState(empty);
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));
  // Anything typed (the job chosen by default isn't typing) is lost by leaving: ask first.
  const typed = [form.title, form.employer, form.description, form.interview_date, form.notes].some((v) => v.trim());
  useLeaveWarning(typed, "the new target job");
  // Kept in this browser while unfinished; offered back after a reload (Volume 9, prompt 2).
  const draft = useFormDraft<typeof empty>({
    storageKey: formDraftKey(user?.id ?? "anon", "target", "new"), form, baseline: empty, base: null,
    isForm: (v): v is typeof empty => isTextForm(v, ["title", "employer", "description", "track", "interview_date", "notes"]),
    enabled: Boolean(user),
  });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      const t = await create.mutateAsync({
        title: form.title, employer: form.employer || null, description: form.description, track: form.track,
        interview_date: form.interview_date || null, notes: form.notes || null,
      });
      draft.accepted(form, form); // made: its copy goes
      allowLeaveAfterSave(); // the one move this save allows: to the target it made
      navigate(`/targets/${t.id}`);
    } catch {
      /* shown below */
    }
  }

  return (
    <Card className="stack new-target">
      {draft.offer && (
        <FormDraftOffer what="a new target job" at={draft.offer.at} onDiscard={draft.discard}
          onRestore={() => { const d = draft.restore(); if (d) setForm(d.form); }} />
      )}
      <form className="stack" onSubmit={onSubmit} aria-labelledby="new-target-title">
        <h2 className="section-title" id="new-target-title">New target role</h2>
        <div className="goals-page__row">
          <label className="field"><span className="field__label">Role title</span>
            <input className="input" required maxLength={120} value={form.title} onChange={(e) => set("title")(e.target.value)} /></label>
          <label className="field"><span className="field__label">Employer (optional)</span>
            <input className="input" maxLength={120} value={form.employer} onChange={(e) => set("employer")(e.target.value)} /></label>
        </div>
        <CareerSelect value={form.track} onChange={set("track")} />
        <div className="field">
          <label className="field__label" htmlFor="new-target-jd">Job description</label>
          <textarea id="new-target-jd" className="input target-jd" required rows={12} maxLength={MAX_DESCRIPTION} value={form.description}
            aria-describedby="jd-help" placeholder="Paste the text of the posting here" onChange={(e) => set("description")(e.target.value)} />
          <span id="jd-help" className="subtle">{form.description.length.toLocaleString()} of {MAX_DESCRIPTION.toLocaleString()} characters. Pasted text is only read for requirements; it's never treated as instructions. Requirements are found by rules, not AI, and you can correct them.</span>
        </div>
        <div className="goals-page__row">
          <label className="field"><span className="field__label">Interview date (optional)</span>
            <input className="input" type="date" value={form.interview_date} onChange={(e) => set("interview_date")(e.target.value)} /></label>
          <label className="field"><span className="field__label">Notes about the interview (optional)</span>
            <input className="input" maxLength={2000} value={form.notes} onChange={(e) => set("notes")(e.target.value)} /></label>
        </div>
        <InlineError error={create.error} />
        <FormDraftStatus changed={typed} kept={draft.kept} competing={draft.competing} copyText={() => [form.title, form.employer, form.description, form.notes].filter(Boolean).join("\n\n")} />
        <div className="row">
          <Button type="submit" variant="primary" loading={create.isPending} disabled={!form.title.trim() || !form.description.trim()}>Find requirements</Button>
          <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}
