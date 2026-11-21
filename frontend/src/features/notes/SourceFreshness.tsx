import { useEffect, useRef, useState } from "react";

import { api } from "@/api/endpoints";
import type { NoteFreshness } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/States";

/**
 * Whether a note's source changed since it was captured (docs/STORY_FRESHNESS.md, "Notes"): above
 * the snapshot, the server's notice in its own words, the change side by side when the content
 * keeps both versions (otherwise what its authors said changed), and "Mark reviewed" for the
 * version shown. The note itself is never changed; the notice clears until the source changes
 * again.
 */
export function SourceFreshness({ noteId, freshness, onReviewed }: {
  noteId: string;
  freshness: NoteFreshness;
  onReviewed: (f: NoteFreshness) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<string | null>(null);
  const status = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (done) status.current?.focus(); }, [done]);
  const f = freshness;
  if (f.state === "current" || f.state === "unavailable") {
    return done ? <p className="banner banner--success" role="status" tabIndex={-1} ref={status}>{done}</p> : null;
  }
  const changes = f.changes ?? [];
  const notes = f.change_notes ?? [];
  const askable = (f.state === "needs_review" || f.state === "unknown") && f.current_version !== null;
  const shown = f.current_version;

  async function markReviewed() {
    if (shown === null) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.reviewNoteSource(noteId, shown);
      setDone(next.state === "current" ? `${next.text} Your note wasn't changed.` : null);
      onReviewed(next);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="stack-sm note-freshness" role="region" aria-label="Source updated">
      <h2 className="section-title">{f.state === "retired" ? "Source retired" : f.state === "unknown" ? "Source version not known" : "Source updated"}</h2>
      <p>{f.text}</p>
      {changes.length > 0 && (
        <div className="stack-sm">
          {changes.map((c) => (
            <div key={c.field} className="note-freshness__change">
              <h3 className="note-freshness__field">{c.field}</h3>
              <div className="note-freshness__sides">
                <div>
                  <p className="subtle">When you captured it{f.reviewed_version ? " or last reviewed it" : ""}</p>
                  <blockquote className="note-quote">{c.before}</blockquote>
                </div>
                <div>
                  <p className="subtle">Now (version {f.current_version})</p>
                  <blockquote className="note-quote">{c.after}</blockquote>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      {notes.length > 0 && (
        <div>
          <p className="subtle">What the {f.kind === "problem" ? "coding problem" : f.kind}'s authors said changed:</p>
          <ul className="mini-list">{notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </div>
      )}
      {askable && (
        <span className="row">
          <Button size="sm" loading={busy} onClick={() => void markReviewed()}>Mark reviewed (version {shown})</Button>
          <span className="subtle">Records that you looked at it; your note stays exactly as it is.</span>
        </span>
      )}
      <InlineError error={error} />
    </Card>
  );
}
