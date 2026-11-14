import { useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useStories, useTargets } from "@/api/queries";
import type { Application } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/States";
import { COMPETENCY_LABEL } from "@/features/stories/labels";

/** The server's limit on stories linked to one application (docs/BACKLINKS.md). */
export const MAX_LINKED_STORIES = 20;
/** With more stories than this, a box to find one by its title. */
const FIND_FROM = 8;

/**
 * Linked preparation: a job target and the stories to prepare for this application (Volume 11,
 * prompt 6; docs/BACKLINKS.md). Each story is linked or unlinked on its own, so a page showing an
 * older list can't undo a link made elsewhere, and sending it again after a lost reply is safe.
 * One list in a fixed order (checking a box doesn't move it), with an archived story that's still
 * linked shown and labelled so it can be unlinked. Links point to your stories; nothing is copied.
 */
export function LinksCard({ a, onDone }: { a: Application; onDone: (a: Application) => void }) {
  const targets = useTargets();
  const stories = useStories({});
  const qc = useQueryClient();
  const [error, setError] = useState<unknown>(null);
  const [targetPending, setTargetPending] = useState<string | null>(null);
  // The change being sent for each story, shown at once; the server's answer replaces it.
  const [sending, setSending] = useState<Record<string, boolean>>({});
  const [lost, setLost] = useState<{ id: string; title: string; linked: boolean } | null>(null);
  const [find, setFind] = useState("");
  const limitId = useId();

  async function saveTarget(id: string) {
    setError(null);
    setTargetPending(id);
    try { onDone(await api.updateApplication(a.id, id ? { target_id: id, clear: [] } : { clear: ["target_id"] })); }
    catch (e) { setError(e); }
    finally { setTargetPending(null); }
  }

  async function setLinked(id: string, title: string, linked: boolean) {
    setError(null);
    setLost(null);
    setSending((now) => ({ ...now, [id]: linked }));
    try {
      onDone(await api.linkApplicationStory(a.id, id, linked));
      void qc.invalidateQueries({ queryKey: ["me", "story", id, "used-in"] });
    } catch (e) {
      if (e instanceof ApiError && (e.code === "network_error" || e.status >= 500)) {
        setLost({ id, title, linked });
        void qc.invalidateQueries({ queryKey: ["me", "application", a.id] }); // show what the server has, if it can be read
      } else {
        setError(e);
      }
    } finally {
      setSending(({ [id]: _sent, ...rest }) => rest);
    }
  }

  const linked = new Set(a.stories.map((s) => s.id));
  const on = (id: string) => (id in sending ? sending[id]! : linked.has(id));
  const full = linked.size >= MAX_LINKED_STORIES;
  // Your active stories, and any archived one that's still linked here (so it can be unlinked).
  const active = stories.data ?? [];
  const rows = [
    ...active.map((s) => ({ id: s.id, title: s.title, archived: false, competencies: s.competencies })),
    ...a.stories.filter((s) => !active.some((x) => x.id === s.id)).map((s) => ({ id: s.id, title: s.title, archived: s.archived, competencies: [] })),
  ];
  const words = find.toLowerCase().split(/\s+/).filter(Boolean);
  const shown = rows.filter((s) => words.every((w) => s.title.toLowerCase().includes(w)));
  const target = targetPending ?? a.target?.id ?? "";

  return (
    <Card className="stack-sm">
      <h2 className="section-title">Linked preparation</h2>
      <label className="field"><span className="field__label">Job target</span>
        <select className="select" value={target} onChange={(e) => void saveTarget(e.target.value)}>
          <option value="">None</option>
          {(targets.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
        </select>
      </label>
      <fieldset className="stack-sm links-card__stories">
        <legend className="field__label">Stories to prepare</legend>
        {a.stories.length > 0 && (
          <p className="subtle">
            Linked ({a.stories.length}):{" "}
            {a.stories.map((s, i) => (
              <span key={s.id}>{i > 0 && ", "}<Link to={`/stories/${s.id}`} state={{ from: `/applications/${a.id}`, fromLabel: "Back to the application" }}>{s.title}</Link>{s.archived && " (archived)"}</span>
            ))}
          </p>
        )}
        {rows.length === 0 && <p className="subtle">No stories yet. <Link to="/stories/new">Write one</Link>.</p>}
        {rows.length > FIND_FROM && (
          <label className="field"><span className="field__label">Find a story</span>
            <input className="input" type="search" value={find} onChange={(e) => setFind(e.target.value)} />
          </label>
        )}
        {words.length > 0 && <p className="subtle" aria-live="polite">{shown.length} of {rows.length} shown.</p>}
        {shown.map((s) => (
          <label key={s.id} className="checkbox">
            <input type="checkbox" checked={on(s.id)} disabled={!on(s.id) && full} aria-describedby={full ? limitId : undefined}
              onChange={(e) => void setLinked(s.id, s.title, e.target.checked)} />
            <span>
              {s.title}{s.archived && <>{" "}<span className="subtle">(archived)</span></>}
              {s.competencies.length > 0 && <>{" "}<span className="subtle">· {s.competencies.slice(0, 2).map((c) => COMPETENCY_LABEL[c]).join(", ")}</span></>}
            </span>
          </label>
        ))}
        {full && <p className="subtle" id={limitId}>Up to {MAX_LINKED_STORIES} stories per application: unlink one to add another.</p>}
      </fieldset>
      {lost && (
        <div className="banner banner--warning stack-sm" role="alert">
          <p>No reply came, so it isn't known whether “{lost.title}” was {lost.linked ? "linked" : "unlinked"}. Trying again is safe: it's done once either way.</p>
          <span className="row"><Button size="sm" onClick={() => void setLinked(lost.id, lost.title, lost.linked)}>Try again</Button></span>
        </div>
      )}
      <p className="subtle">Links point to your target and stories; nothing is copied. Your story shows where it's used.</p>
      <InlineError error={error} />
    </Card>
  );
}
