import { useId } from "react";

import type { ReviewPreview } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";

/**
 * What the coach will read (docs/COACH_CONTEXT.md): each private item exactly as it's sent, after
 * secret-looking strings are replaced and long input cut, with where it comes from and whether it
 * can be left out. Shown as text: anything written inside it is never followed or rendered. The
 * coach's fixed instructions are one sentence here, not a prompt viewer.
 */
export function CoachContext({ preview, share, onShare, stale, changed, busy, onSend, onCancel, onCheckAgain }: {
  preview: ReviewPreview;
  share: boolean;
  onShare(share: boolean): void;
  /** The code in the editor isn't what this preview shows. */
  stale: boolean;
  /** Why a send was refused and this preview is a fresh one. */
  changed: string | null;
  busy: boolean;
  onSend(): void;
  onCancel(): void;
  onCheckAgain(): void;
}) {
  const ids = useId();
  const canChooseVerdict = preview.items.some((i) => i.key === "verdict") || preview.left_out.some((l) => l.reason === "removed");
  return (
    <section className="coach-context stack-sm" aria-labelledby={`${ids}-title`}>
      <h3 className="section-title" id={`${ids}-title`}>What the coach will read</h3>
      {changed && <p className="banner banner--warning" role="alert">{changed}</p>}
      <p>
        <strong>Read by:</strong> {preview.recipient}.{preview.fallback ? ` ${preview.fallback}` : ""}
      </p>
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
            {item.key === "verdict" && (
              <label className="checkbox">
                <input type="checkbox" checked={share} disabled={busy} onChange={(e) => onShare(e.target.checked)} />
                Send the judge's verdict
              </label>
            )}
          </li>
        ))}
        {preview.left_out.map((l) => (
          <li key={l.key} className="coach-context__item stack-sm">
            <div className="row"><strong>{l.label}</strong><Badge>Not sent</Badge></div>
            <p className="subtle">
              {l.reason === "removed" ? "You left it out." : "It isn't available any more, so it won't be sent."}
            </p>
            {l.reason === "removed" && canChooseVerdict && (
              <label className="checkbox">
                <input type="checkbox" checked={share} disabled={busy} onChange={(e) => onShare(e.target.checked)} />
                Send the judge's verdict
              </label>
            )}
          </li>
        ))}
      </ul>
      {preview.required_public.map((p) => <p key={p}><strong>Also sent:</strong> {p}</p>)}
      <p className="subtle">{preview.instructions}</p>
      <p className="subtle">
        Checking this is free. Sending uses one of the {preview.remaining_today} coaching request{preview.remaining_today === 1 ? "" : "s"} you
        have left today.
      </p>
      {stale && (
        <p className="banner banner--warning" role="status">
          Your code changed since this was checked, so it isn't what would be sent.{" "}
          <Button size="sm" variant="secondary" onClick={onCheckAgain}>Check again</Button>
        </p>
      )}
      <div className="row">
        <Button variant="primary" loading={busy} disabled={stale || preview.remaining_today === 0} onClick={onSend}>Send for review</Button>
        <Button variant="ghost" disabled={busy} onClick={onCancel}>Cancel</Button>
      </div>
    </section>
  );
}
