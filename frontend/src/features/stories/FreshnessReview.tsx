import { Link } from "react-router-dom";

import type { Freshness } from "@/api/types";
import { Button } from "@/components/Button";

export type Decision = "refresh" | "keep";

/**
 * A story that changed after something was prepared from it (docs/STORY_FRESHNESS.md): the server's
 * sentence, what changed side by side, and the learner's two choices, each bound to the version shown
 * here. Nothing is refreshed by itself; "current" shows nothing.
 */
export function FreshnessReview({ f, title, href, linkState, busy, disabledNote, what, onDecide, preparedLabel = "As prepared" }: {
  f: Freshness;
  title: string;
  href: string;
  linkState?: unknown;
  busy: boolean;
  /** Set when the decision can't be sent right now (e.g. unsaved edits): why. */
  disabledNote?: string;
  /** Who the change is for, after "Use version N" (e.g. "in this kit", "for these requirements"). */
  what: string;
  onDecide: (decision: Decision, reviewedRevision: number) => void;
  /** The earlier column's heading: "As prepared" (a kit), "As linked" (a requirement link). */
  preparedLabel?: string;
}) {
  if (f.state === "current") return null;
  const now = f.current_revision;
  const changes = f.changes ?? [];
  const lineage = f.lineage ?? [];
  const then = f.prepared_revision;
  const decidable = now != null && (f.state === "needs_review" || f.state === "unknown" || f.state === "kept");
  return (
    <div className={`freshness freshness--${f.state}`}>
      <p>
        <strong>“{title}”</strong>: {f.text}{" "}
        {now != null && <Link to={href} state={linkState}>Open the story</Link>}
      </p>
      {changes.length > 0 && f.state !== "kept" && (
        <div className="freshness__table">
          <table>
            <caption className="visually-hidden">What changed in “{title}”</caption>
            <thead>
              <tr>
                <th scope="col">Part</th>
                <th scope="col">{preparedLabel}{then != null ? ` (version ${then})` : ""}</th>
                <th scope="col">Now{now != null ? ` (version ${now})` : ""}</th>
              </tr>
            </thead>
            <tbody>
              {changes.map((c) => (
                <tr key={c.field}>
                  <th scope="row">{c.field}</th>
                  <td>{c.before === null ? <span className="subtle">Not kept any more</span> : c.before || <span className="subtle">(empty)</span>}</td>
                  <td>{c.after || <span className="subtle">(empty)</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {decidable && (
        <div className="row freshness__actions">
          <Button size="sm" variant="secondary" loading={busy} disabled={!!disabledNote} onClick={() => onDecide("refresh", now)}>
            Use version {now} {what}
          </Button>
          {f.state === "needs_review" && then != null && (
            <Button size="sm" variant="ghost" disabled={busy || !!disabledNote} onClick={() => onDecide("keep", now)}>
              Keep version {then}
            </Button>
          )}
        </div>
      )}
      {decidable && disabledNote && <p className="subtle">{disabledNote}</p>}
      {lineage[0] && f.state !== "kept" && <p className="subtle">Last decision: {lineage[0].text}</p>}
    </div>
  );
}
