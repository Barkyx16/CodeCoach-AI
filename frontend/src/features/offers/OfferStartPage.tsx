import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useOfferCase } from "@/api/queries";
import { BackLink } from "@/components/BackLink";
import { Button } from "@/components/Button";
import { ErrorState, InlineError, LoadingState } from "@/components/States";

import { FactCard } from "./FactCard";

/** /offers/:caseId: the fictional fact card, optional goals in the learner's own words, then start. */
export function OfferStartPage() {
  const { caseId = "" } = useParams();
  const c = useOfferCase(caseId);
  const navigate = useNavigate();
  const [goals, setGoals] = useState(["", "", ""]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  if (c.isPending) return <LoadingState label="Loading the offer…" />;
  if (c.isError) return <div className="page"><ErrorState error={c.error} onRetry={() => void c.refetch()} /></div>;

  async function start(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api.startOfferRehearsal({ case_id: caseId, goals: goals.map((g) => g.trim()).filter(Boolean) });
      navigate(`/offers/rehearsals/${r.id}`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page offers-start">
      <BackLink fallback={{ to: "/offers", label: "Offer conversations" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">OFFER CONVERSATION · FICTIONAL</p>
          <h1 className="page__title">{c.data.title}</h1>
          <p className="page__subtitle">Three parts: {c.data.phases.map((p) => p.title.toLowerCase()).join(", then ")}. You can stop at any point.</p>
        </div>
      </div>
      <FactCard card={c.data} />
      <form className="card stack-sm" onSubmit={(e) => void start(e)} aria-labelledby="offer-goals">
        <h2 className="section-title" id="offer-goals">Your goals (optional)</h2>
        <p className="subtle">
          What you'd like from the conversation, in your words: more pay, a later start, time to decide, or to say no. They're kept
          apart from the card, shown back in the debrief, and never sent anywhere.
        </p>
        {goals.map((g, i) => (
          <label key={i} className="field">
            <span className="field__label">Goal {i + 1}</span>
            <input className="input" maxLength={200} value={g} onChange={(e) => setGoals((cur) => cur.map((x, j) => (j === i ? e.target.value : x)))} />
          </label>
        ))}
        <p className="subtle">Don't enter real employer details here: this rehearsal only uses the fictional card above.</p>
        <span className="row"><Button type="submit" variant="primary" loading={busy}>Start the rehearsal</Button></span>
        <InlineError error={error} />
      </form>
    </div>
  );
}
