import { useParams } from "react-router-dom";

import { useComparison, useRetryQuestion } from "@/api/queries";
import type { AnswerSource, Comparison } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { PrivateUnavailable } from "@/components/Unavailable";
import { isGone } from "@/lib/errors";
import { clearStoredDraft, useStoredDraft } from "@/hooks/useStoredDraft";
import { useInterviewerVoice } from "@/features/voice/useInterviewerVoice";
import { VoiceComposer } from "@/features/voice/VoiceComposer";
import { useVoicePrefs } from "@/features/voice/voicePrefs";

/** Retry one interview question. The original answer stays as it was; the new one is compared to it. */
export function RetryPage() {
  const { id = "", index = "0" } = useParams();
  const i = Number(index);
  const comparison = useComparison(id, i);
  const retry = useRetryQuestion(id, i);
  const key = `codecoach.retry.${id}.${i}`;
  const [draft, setDraft] = useStoredDraft(key);
  const [prefs] = useVoicePrefs();
  const voice = useInterviewerVoice(prefs);
  if (comparison.isPending) return <LoadingState label="Loading the question…" />;
  if (comparison.isError && isGone(comparison.error)) return <PrivateUnavailable what="answer" list={{ to: "/history?type=interview", label: "All your interviews" }} />;
  if (comparison.isError) return <div className="page"><BackLink fallback={{ to: `/interviews/${id}`, label: "Back to the review" }} /><ErrorState error={comparison.error} onRetry={() => void comparison.refetch()} /></div>;
  const c = comparison.data;

  async function submit(source: AnswerSource): Promise<boolean> {
    try {
      await retry.mutateAsync({ answer: draft.trim(), source });
      clearStoredDraft(key);
      setDraft("");
      return true;
    } catch {
      return false; // draft kept; error shown
    }
  }

  return (
    <div className="page retry-page">
      <BackLink fallback={{ to: `/interviews/${id}?item=q${i}`, label: "Back to the review" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">RETRY ONE QUESTION</p>
          <h1 className="page__title">{c.question_title}</h1>
          <p className="page__subtitle">Your interview answer is kept exactly as it was. A retry is saved as a separate attempt with its own feedback.</p>
        </div>
      </div>
      <Card className="question-page__prompt"><p>{c.prompt}</p></Card>
      {c.original && (
        <details className="card retry-page__original">
          <summary>Your original answer ({c.original.score}/100)</summary>
          <blockquote className="round-result__answer">{c.original.answer}</blockquote>
        </details>
      )}
      <VoiceComposer id="retry-answer" label="Your new answer" value={draft} onChange={setDraft} onSubmit={submit}
        submitting={retry.isPending} maxLength={6000} submitLabel="Get feedback and compare" voice={voice}
        placeholder="Answer it again, using the feedback…" hint="Your draft is saved in this browser until you send it." />
      <InlineError error={retry.error} />
      {c.latest && <ComparisonView c={c} />}
    </div>
  );
}

export function ComparisonView({ c }: { c: Comparison }) {
  return (
    <section className="card stack comparison" aria-labelledby="comparison-title">
      <h2 className="section-title" id="comparison-title">How your latest attempt compares</h2>
      <p className={c.comparable ? "subtle" : "banner banner--warning"}>{c.comparability_note}</p>
      <div className="comparison__grid">
        <div className="stack">
          <h3 className="assessment__h">Original{c.original ? ` · ${c.original.score}/100` : ""}</h3>
          {c.original ? <blockquote className="round-result__answer">{c.original.answer}</blockquote> : <p className="subtle">No answer in the interview.</p>}
        </div>
        <div className="stack">
          <h3 className="assessment__h">Latest retry · {c.latest!.score}/100{c.score_change !== null && c.score_change !== undefined ? ` (${c.score_change >= 0 ? "+" : ""}${c.score_change})` : ""}</h3>
          <blockquote className="round-result__answer">{c.latest!.answer}</blockquote>
        </div>
      </div>
      {c.classification && !c.classification.points_comparable ? (
        <p className="subtle">What each covered is on its own feedback; they aren't compared point by point.</p>
      ) : <div className="comparison__lists">
        <div><h3 className="assessment__h">Improved</h3>{c.improved.length ? <ul className="mini-list">{c.improved.map((p) => <li key={p}>✓ {p}</li>)}</ul> : <p className="subtle">Nothing new covered yet.</p>}</div>
        <div><h3 className="assessment__h">Still needs attention</h3>{c.still_missing.length ? <ul className="mini-list">{c.still_missing.map((p) => <li key={p}>○ {p}</li>)}</ul> : <p className="subtle">Nothing missing.</p>}</div>
        {c.newly_missing.length > 0 && <div><h3 className="assessment__h">Covered before, missing now</h3><ul className="mini-list">{c.newly_missing.map((p) => <li key={p}>! {p}</li>)}</ul></div>}
      </div>}
      {c.retries.length > 1 && <p className="subtle">{c.retries.length} retries so far; the latest is shown. Every attempt stays in your History.</p>}
    </section>
  );
}
