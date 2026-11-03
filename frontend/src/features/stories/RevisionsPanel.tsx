import { useState } from "react";

import { api } from "@/api/endpoints";
import { useStoryRevisions } from "@/api/queries";
import type { Story, StoryRevision } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/States";
import { formatDateTime } from "@/lib/format";

import { SECTION_LABEL, SECTIONS } from "./labels";

const REASON = { created: "Written", edited: "Edited", assisted: "Edited with the writing check", restored: "Restored" } as const;

/** Every saved version. Restoring one saves it as a new version; nothing is deleted. */
export function RevisionsPanel({ story, onRestored }: { story: Story; onRestored: (s: Story) => void }) {
  const revisions = useStoryRevisions(story.id);
  const [open, setOpen] = useState<number | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function restore(r: StoryRevision) {
    if (!window.confirm(`Bring back version ${r.revision}? It's saved as a new version; the current one stays in this list.`)) return;
    setBusy(true);
    setError(null);
    try {
      onRestored(await api.restoreStoryRevision(story.id, r.revision, story.revision));
      void revisions.refetch();
      setOpen(null);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="stack-sm">
      <h2 className="section-title">Saved versions</h2>
      {revisions.data && (
        <ol className="revision-list">
          {revisions.data.map((r) => (
            <li key={r.revision}>
              <button type="button" className="link-button" aria-expanded={open === r.revision} onClick={() => setOpen(open === r.revision ? null : r.revision)}>
                Version {r.revision}
              </button>{" "}
              <span className="subtle">· {REASON[r.reason]} · {formatDateTime(r.created_at)}{r.revision === story.revision ? " · current" : ""}</span>
              {open === r.revision && (
                <div className="revision-list__detail stack-sm">
                  <p><strong>{String(r.fields.title ?? "")}</strong></p>
                  {SECTIONS.map((s) => r.fields[s] ? <p key={s}><span className="eyebrow">{SECTION_LABEL[s].toUpperCase()}</span><br />{String(r.fields[s])}</p> : null)}
                  {r.revision !== story.revision && <span><Button size="sm" loading={busy} onClick={() => void restore(r)}>Restore this version</Button></span>}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
      <InlineError error={error ?? revisions.error} />
    </Card>
  );
}
