import type { Engagement } from "@/api/types";
import { Button } from "@/components/Button";

/** A shape per state, so the state never depends on color alone (the text label is always shown too). */
const GLYPH: Record<Engagement["state"], string> = {
  not_enough_evidence: "○",
  more_detail: "◔",
  following: "◑",
  explore_further: "●",
};

export const ENGAGEMENT_DISCLAIMER =
  "A simulation based only on what your answer says (relevance, specific examples, structure, detail). " +
  "It isn't a real person's opinion, doesn't judge your voice or how you speak, and doesn't predict hiring decisions.";

/** "Simulated interviewer engagement" for the latest answer, hideable during the interview. */
export function EngagementMeter({ engagement, visible, onToggle }: {
  engagement: Engagement | null; visible: boolean; onToggle: () => void;
}) {
  const state = engagement?.state ?? "not_enough_evidence";
  return (
    <section className="card stack engagement" aria-labelledby="engagement-title">
      <div className="engagement__head">
        <h2 className="section-title" id="engagement-title">Simulated interviewer engagement</h2>
        <Button size="sm" variant="ghost" aria-expanded={visible} onClick={onToggle}>{visible ? "Hide" : "Show"}</Button>
      </div>
      {visible ? (
        <>
          <p className={`engagement__state engagement__state--${state}`} role="status">
            <span aria-hidden="true" className="engagement__glyph">{GLYPH[state]}</span>
            <strong>{engagement?.label ?? "Not enough evidence yet"}</strong>
          </p>
          <p className="engagement__reason">
            {engagement ? engagement.reason.replace(/^[^:]+:\s*/, "") : "Answer the question and this updates from what your answer contains."}
          </p>
          {engagement && engagement.evidence.length > 0 && (
            <details className="engagement__evidence">
              <summary>What it's based on</summary>
              <ul className="mini-list">{engagement.evidence.map((e) => <li key={e}>{e}</li>)}</ul>
            </details>
          )}
          <p className="subtle engagement__note">{ENGAGEMENT_DISCLAIMER}</p>
        </>
      ) : (
        <p className="subtle">Hidden. You can review it after the interview.</p>
      )}
    </section>
  );
}

/** Compact read-only version for results and transcripts. */
export function EngagementNote({ engagement }: { engagement: Engagement }) {
  return (
    <p className={`engagement-note engagement__state--${engagement.state}`}>
      <span aria-hidden="true" className="engagement__glyph">{GLYPH[engagement.state]}</span>
      <span><strong>{engagement.label}.</strong> {engagement.reason.replace(/^[^:]+:\s*/, "")}</span>
    </p>
  );
}
