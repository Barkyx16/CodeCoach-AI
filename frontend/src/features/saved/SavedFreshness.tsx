import { useState } from "react";

import type { NoteFreshness } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";

import { freshnessBadge } from "./freshness";

/**
 * Whether a saved item's source changed since it was saved or added (Volume 14, prompt 7;
 * docs/STORY_FRESHNESS.md, "Saved items and collections"): the same server rule as notes, shown as
 * a badge with what changed under it, and "Mark reviewed" for the version shown. The item itself
 * is never changed, moved or unsaved; a review clears the badge until the source changes again.
 */
export function SavedFreshness({ title, freshness, review }: {
  title: string;
  freshness: NoteFreshness | null | undefined;
  review: (version: number) => Promise<unknown>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<string | null>(null);
  const f = freshness;
  const badge = freshnessBadge(f);
  if (!f || !badge) {
    return done ? <p className="subtle" role="status">{done}</p> : null;
  }
  const askable = (f.state === "needs_review" || f.state === "unknown") && f.current_version !== null;
  const shown = f.current_version;
  const changes = f.changes ?? [];
  const notes = f.change_notes ?? [];

  async function markReviewed() {
    if (shown === null) return;
    setBusy(true);
    setError(null);
    try {
      await review(shown);
      setDone(`Marked reviewed at version ${shown}. Nothing about the saved item changed.`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="saved-freshness stack-sm">
      <Badge tone={f.state === "needs_review" ? "warning" : "neutral"}>{badge}</Badge>
      <details className="saved-freshness__details">
        <summary>{f.state === "needs_review" ? "What changed" : "Why"}<span className="visually-hidden">: {title}</span></summary>
        <div className="stack-sm">
          <p>{f.text}</p>
          {changes.map((c) => (
            <div key={c.field} className="note-freshness__change">
              <h3 className="note-freshness__field">{c.field}</h3>
              <div className="note-freshness__sides">
                <div>
                  <p className="subtle">When you saved it{f.reviewed_version ? " or last reviewed it" : ""}</p>
                  <blockquote className="note-quote">{c.before}</blockquote>
                </div>
                <div>
                  <p className="subtle">Now (version {f.current_version})</p>
                  <blockquote className="note-quote">{c.after}</blockquote>
                </div>
              </div>
            </div>
          ))}
          {notes.length > 0 && (
            <div>
              <p className="subtle">What the {f.kind === "problem" ? "coding problem" : f.kind}'s authors said changed:</p>
              <ul className="mini-list">{notes.map((n) => <li key={n}>{n}</li>)}</ul>
            </div>
          )}
          {askable && (
            <span className="row">
              <Button size="sm" loading={busy} aria-label={`Mark reviewed (version ${shown}): ${title}`} onClick={() => void markReviewed()}>
                Mark reviewed (version {shown})
              </Button>
              <span className="subtle">Records that you looked at it; it stays saved, where it is.</span>
            </span>
          )}
          <InlineError error={error} />
        </div>
      </details>
    </div>
  );
}
