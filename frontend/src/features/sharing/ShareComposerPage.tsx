import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import type { ShareCreated, ShareSelection } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

import { LinkPanel } from "./LinkPanel";
import { SharedSnapshot } from "./SharedSnapshot";

const EXPIRY = [
  { days: 1, label: "1 day" },
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
] as const;

/**
 * Share one answer for feedback: choose exactly what to include, see the reviewer's view, confirm
 * who can see it, then copy the link. Nothing is created until "Create link".
 */
export function ShareComposerPage() {
  const [params] = useSearchParams();
  const answerId = params.get("answer") ?? "";
  const qc = useQueryClient();
  const [excluded, setExcluded] = useState<Set<number>>(new Set());
  const [includeAI, setIncludeAI] = useState(false);
  const [includeFollowup, setIncludeFollowup] = useState(true);
  const [note, setNote] = useState("");
  const [days, setDays] = useState<1 | 7 | 30>(7);
  const [acknowledged, setAcknowledged] = useState(false);
  const [created, setCreated] = useState<ShareCreated | null>(null);

  const debouncedNote = useDebouncedValue(note.trim(), 300); // don't ask for a preview on every keystroke
  const selection: ShareSelection = { answer_id: answerId, include_ai_feedback: includeAI, include_followup: includeFollowup, note: debouncedNote };
  // The full list of sentences comes from the first preview; after that the selection is explicit.
  const all = useQuery({
    queryKey: ["me", "share-preview", answerId, "all"],
    queryFn: () => api.sharePreview({ answer_id: answerId, include_ai_feedback: false, include_followup: true, note: "" }),
    enabled: Boolean(answerId),
    staleTime: Infinity,
  });
  const indices = (all.data?.source_sentences ?? []).map((s) => s.index).filter((i) => !excluded.has(i));
  const preview = useQuery({
    queryKey: ["me", "share-preview", { ...selection, sentences: indices }],
    queryFn: () => api.sharePreview({ ...selection, sentences: indices }),
    enabled: Boolean(answerId) && all.isSuccess && indices.length > 0,
    placeholderData: keepPreviousData,
    retry: false,
  });
  const create = useMutation({
    mutationFn: () => api.createShare({
      answer_id: answerId, sentences: indices, include_ai_feedback: includeAI, include_followup: includeFollowup,
      note: note.trim(), expires_in_days: days, acknowledge_link_access: acknowledged,
    }),
    onSuccess: (result) => {
      setCreated(result);
      void qc.invalidateQueries({ queryKey: ["me", "shares"] });
    },
  });

  if (!answerId) {
    return <div className="page"><ErrorState error={new Error("Choose an answer to share: open it and use “Ask someone for feedback”.")} /></div>;
  }
  if (all.isPending) return <LoadingState label="Loading your answer…" />;
  if (all.isError) return <div className="page"><ErrorState error={all.error} onRetry={() => void all.refetch()} /></div>;

  if (created) {
    return (
      <div className="page share-page">
        <div className="page__header">
          <div>
            <p className="eyebrow">SHARED FOR FEEDBACK</p>
            <h1 className="page__title">Your link is ready</h1>
            <p className="page__subtitle">Send it yourself to someone you trust. CodeCoach doesn't email or message anyone.</p>
          </div>
        </div>
        <LinkPanel created={created} />
        <p className="row">
          <Link className="btn btn--primary btn--md" to={`/shares/${created.share.id}`}>See this share and its feedback</Link>
          <Link className="btn btn--ghost btn--md" to="/shares">All shared answers</Link>
        </p>
      </div>
    );
  }

  const source = all.data;
  const toggle = (index: number) => setExcluded((current) => {
    const next = new Set(current);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    return next;
  });
  const view = indices.length > 0 ? preview.data?.view : undefined;

  return (
    <div className="page share-page">
      <BackLink />
      <div className="page__header">
        <div>
          <p className="eyebrow">ASK FOR FEEDBACK</p>
          <h1 className="page__title">Share an answer with someone you trust</h1>
          <p className="page__subtitle">Choose what they see. They get a private link to a copy of it; nothing else from your account.</p>
        </div>
      </div>

      <div className="share-composer">
        <form className="card stack" aria-labelledby="choose-title" onSubmit={(e) => { e.preventDefault(); if (acknowledged && indices.length) create.mutate(); }}>
          <h2 className="section-title" id="choose-title">Choose what to share</h2>
          <fieldset className="field">
            <legend className="field__label">Sentences of your answer</legend>
            <p className="subtle" id="sentences-hint">Untick anything you'd rather keep to yourself. The reviewer sees where something was left out.</p>
            <ul className="share-sentences" aria-describedby="sentences-hint">
              {source.source_sentences.map((s) => (
                <li key={s.index}>
                  <label className="checkbox share-sentences__item">
                    <input type="checkbox" checked={!excluded.has(s.index)} onChange={() => toggle(s.index)} />
                    <span><span className="share-sentences__n">{s.index + 1}.</span> {s.text}</span>
                  </label>
                </li>
              ))}
            </ul>
            {indices.length === 0 && <p className="field__error" role="alert">Choose at least one sentence.</p>}
          </fieldset>
          {source.has_followup && (
            <label className="checkbox">
              <input type="checkbox" checked={includeFollowup} onChange={(e) => setIncludeFollowup(e.target.checked)} />
              Include the follow-up question and your reply
            </label>
          )}
          <label className="checkbox">
            <input type="checkbox" checked={includeAI} onChange={(e) => setIncludeAI(e.target.checked)} />
            Include CodeCoach's automated feedback (labelled as automated)
          </label>
          <label className="field">
            <span className="field__label">Note to your reviewer <span className="subtle">(optional)</span></span>
            <textarea className="input" rows={3} maxLength={500} value={note} aria-describedby="note-hint"
              placeholder="e.g. Is my example convincing for a charge nurse role?" onChange={(e) => setNote(e.target.value)} />
            <span className="field__hint" id="note-hint">{500 - note.length} characters left. Part of what they see.</span>
          </label>
          <fieldset className="field">
            <legend className="field__label">The link works for</legend>
            <div className="segmented">
              {EXPIRY.map((o) => (
                <label key={o.days} className={`segmented__option${days === o.days ? " segmented__option--active" : ""}`}>
                  <input type="radio" name="expiry" checked={days === o.days} onChange={() => setDays(o.days)} />{o.label}
                </label>
              ))}
            </div>
          </fieldset>
          <p className="subtle">Not included: your name, email, other answers, scores history, goals, notes, target roles or any audio.</p>
          <label className="checkbox share-consent">
            <input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} />
            <span>I understand that <strong>anyone who has the link</strong> can see what I selected until it expires or I turn it off.</span>
          </label>
          <InlineError error={create.error} />
          <Button type="submit" variant="primary" loading={create.isPending} disabled={!acknowledged || indices.length === 0}>Create link</Button>
        </form>

        <Card className="stack share-preview" role="region" aria-label="Preview: what your reviewer sees" tabIndex={0} /* it scrolls on its own: reachable by keyboard */>
          <p className="eyebrow">PREVIEW · WHAT YOUR REVIEWER SEES</p>
          {preview.isError ? <InlineError error={preview.error} />
            : view ? (
              <>
                <SharedSnapshot view={view} idPrefix="preview" />
                <div className="stack-sm">
                  <h2 className="section-title">They're asked</h2>
                  <ul className="mini-list">{view.prompts.map((p) => <li key={p}>{p}</li>)}</ul>
                </div>
              </>
            ) : indices.length === 0 ? <p className="subtle">Nothing selected yet.</p> : <LoadingState label="Updating the preview…" />}
        </Card>
      </div>
    </div>
  );
}
