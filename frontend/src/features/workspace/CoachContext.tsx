import { useId } from "react";

import type { CoachPreview } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";

/** The optional items a learner can leave out, and the checkbox that says so. */
export type ChoiceKey = "verdict" | "compile_output" | "failing_test";
const CHOICE_LABEL: Record<ChoiceKey, string> = {
  verdict: "Send the judge's verdict",
  compile_output: "Send the compiler output",
  failing_test: "Send the failing public test",
};
const isChoice = (key: string): key is ChoiceKey => key in CHOICE_LABEL;

/**
 * What the coach will read (docs/COACH_CONTEXT.md), for a code review, a hint, a failure
 * explanation, a coding interview message or its feedback: each private item exactly as it's
 * sent, after secret-looking strings are replaced and long input cut, with where it comes from
 * and whether it can be left out. Shown as text: anything written inside it is never followed or
 * rendered. The coach's fixed instructions are one sentence here, not a prompt viewer.
 */
export function CoachContext({ preview, choices, onChoose, stale, changed, busy, blocked = false, sendLabel, onSend, onCancel, onCheckAgain, title = "What the coach will read", costNote, budgetBlocks = true }: {
  preview: CoachPreview;
  /** What's chosen for each optional item (sent or not). */
  choices: Partial<Record<ChoiceKey, boolean>>;
  onChoose(key: ChoiceKey, send: boolean): void;
  /** Why what's on screen isn't what this preview shows (the code changed, a newer submission), or null. */
  stale: string | null;
  /** Why a send was refused and this preview is a fresh one. */
  changed: string | null;
  busy: boolean;
  /** Sending has to wait (the server asked for a pause); checking doesn't. */
  blocked?: boolean;
  sendLabel: string;
  onSend(): void;
  onCancel(): void;
  onCheckAgain(): void;
  /** The heading: "What the interviewer reads" for the coding interviewer. */
  title?: string;
  /** What sending costs, when it isn't simply one of today's requests (the interview's feedback). */
  costNote?: string;
  /** Whether no requests left today stops the send (the interview's feedback is scored free instead). */
  budgetBlocks?: boolean;
}) {
  const ids = useId();
  const choice = (key: ChoiceKey) => (
    <label className="checkbox">
      <input type="checkbox" checked={choices[key] ?? true} disabled={busy} onChange={(e) => onChoose(key, e.target.checked)} />
      {CHOICE_LABEL[key]}
    </label>
  );
  const answered = preview.already_answered ?? null;
  return (
    <section className="coach-context stack-sm" aria-labelledby={`${ids}-title`}>
      <h3 className="section-title" id={`${ids}-title`}>{title}</h3>
      {changed && <p className="banner banner--warning" role="alert">{changed}</p>}
      {(preview.about ?? []).length > 0 && (
        <ul className="mini-list coach-context__about">{(preview.about ?? []).map((a) => <li key={a}>{a}</li>)}</ul>
      )}
      {answered && <p className="banner banner--info">{answered}</p>}
      <p>
        <strong>Read by:</strong> {preview.recipient}.{preview.fallback ? ` ${preview.fallback}` : ""}
      </p>
      {/* Names you listed in Settings (docs/PRIVACY.md): what's below is what's sent, with them replaced. */}
      {preview.names_note && <p className="coach-context__names">{preview.names_note}</p>}
      <ul className="coach-context__items">
        {preview.items.map((item) => (
          <li key={item.key} className="coach-context__item stack-sm">
            <div className="row">
              <strong>{item.label}</strong>
              <Badge>{item.required ? "Needed" : "Optional"}</Badge>
              {item.derived && <Badge tone="info">Worked out by CodeCoach</Badge>}
            </div>
            <p className="subtle">{item.source}{item.why_required ? ` ${item.why_required}` : ""}</p>
            {(item.notes ?? []).map((n) => <p key={n} className="subtle">{n}</p>)}
            <pre className="coach-context__text" tabIndex={0} aria-label={`Exactly what's sent: ${item.label}`}>{item.text}</pre>
            {!item.required && isChoice(item.key) && choice(item.key)}
          </li>
        ))}
        {preview.left_out.map((l) => (
          <li key={l.key} className="coach-context__item stack-sm">
            <div className="row"><strong>{l.label}</strong><Badge>Not sent</Badge></div>
            <p className="subtle">
              {l.reason === "removed" ? "You left it out." : "It isn't available any more, so it won't be sent."}
            </p>
            {l.reason === "removed" && isChoice(l.key) && choice(l.key)}
          </li>
        ))}
      </ul>
      {preview.required_public.map((p) => <p key={p}><strong>Also sent:</strong> {p}</p>)}
      <p className="subtle">{preview.instructions}</p>
      <p className="subtle">
        {answered ? "Checking this is free, and so is showing what was kept: nothing is sent." : costNote ?? (
          <>Checking this is free. Sending uses one of the {preview.remaining_today} coaching request{preview.remaining_today === 1 ? "" : "s"} you
          have left today.</>
        )}
      </p>
      {stale && (
        <p className="banner banner--warning" role="status">
          {stale}{" "}
          <Button size="sm" variant="secondary" onClick={onCheckAgain}>Check again</Button>
        </p>
      )}
      <div className="row">
        <Button variant="primary" loading={busy} disabled={blocked || stale !== null || (budgetBlocks && !answered && preview.remaining_today === 0)} onClick={onSend}>{sendLabel}</Button>
        <Button variant="ghost" disabled={busy} onClick={onCancel}>Cancel</Button>
      </div>
    </section>
  );
}

export const CODE_CHANGED = "Your code changed since this was checked, so it isn't what would be sent.";
export const REFUSED = "What the coach would read changed since you checked it, so nothing was sent. This is what it would read now.";
