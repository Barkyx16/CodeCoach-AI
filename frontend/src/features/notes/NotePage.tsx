import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useNote } from "@/api/queries";
import type { KeyPoints, Note } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { formatDateTime, timeAgo } from "@/lib/format";
import { CodeBlock } from "@/features/learn/UnitParts";

import { NoteEditor } from "./NoteEditor";
import { useNoteAutosave } from "./useNoteAutosave";

/** One note: autosaving editor, its source and snapshot, pin/archive/delete and key points. */
export function NotePage() {
  const { id = "" } = useParams();
  if (id === "new") return <NoteScreen key="new" note={null} />;
  return <ExistingNote id={id} />;
}

function ExistingNote({ id }: { id: string }) {
  const note = useNote(id);
  if (note.isPending) return <LoadingState label="Loading note…" />;
  if (note.isError) return <div className="page"><BackLink fallback={{ to: "/notes", label: "Your notebook" }} /><ErrorState error={note.error} onRetry={() => void note.refetch()} /></div>;
  return <NoteScreen key={note.data.id} note={note.data} />;
}

function NoteScreen({ note }: { note: Note | null }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const editor = useNoteAutosave({
    initial: note,
    draftKey: `note-draft:${user?.id ?? "anon"}:${note?.id ?? "new"}`,
    onSaved: (n) => {
      qc.setQueryData(["me", "note", n.id], n);
      void qc.invalidateQueries({ queryKey: ["me", "notes"] });
      if (!note) navigate(`/notes/${n.id}`, { replace: true });
    },
  });
  const current = editor.server;
  const [flagError, setFlagError] = useState<unknown>(null);
  const [points, setPoints] = useState<KeyPoints | null>(null);
  const [pointsError, setPointsError] = useState<unknown>(null);
  const [deleting, setDeleting] = useState(false);

  async function setFlags(flags: { pinned?: boolean; archived?: boolean }) {
    if (!current) return;
    setFlagError(null);
    try {
      const n = await api.updateNote(current.id, flags);
      editor.adopt({ ...n, title: editor.server?.title ?? n.title, body: editor.server?.body ?? n.body, reflection: editor.server?.reflection ?? n.reflection, tags: editor.server?.tags ?? n.tags });
      qc.setQueryData(["me", "note", n.id], n);
      void qc.invalidateQueries({ queryKey: ["me", "notes"] });
    } catch (e) { setFlagError(e); }
  }

  return (
    <div className="page note-page">
      <BackLink fallback={{ to: "/notes", label: "Your notebook" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">NOTE</p>
          <h1 className="page__title">{editor.fields.title.trim() || (note ? "Untitled note" : "New note")}</h1>
          {current && <p className="page__subtitle">Created {formatDateTime(current.created_at)} · updated {timeAgo(current.updated_at)}</p>}
        </div>
        {current && (
          <div className="row">
            {current.pinned && <Badge tone="info">Pinned</Badge>}
            {current.archived && <Badge>Archived</Badge>}
          </div>
        )}
      </div>

      <div className="note-page__layout">
        <div className="stack">
          <NoteEditor editor={editor} autoFocus={!note} />
          {current && current.key_points && current.key_points.length > 0 && (
            <Card className="stack-sm">
              <h2 className="section-title">Key points</h2>
              <ul className="mini-list">{current.key_points.map((p) => <li key={p}>{p}</li>)}</ul>
            </Card>
          )}
        </div>

        <aside className="stack">
          {current?.source && (
            <Card className="stack-sm">
              <h2 className="section-title">Source</h2>
              {current.source.available && current.source.href
                ? <Link to={current.source.href} state={{ from: `/notes/${current.id}`, fromLabel: "Back to the note" }}>{current.source.title}</Link>
                : <p>{current.source.title} <span className="subtle">(no longer available; your note is kept)</span></p>}
              <p className="subtle">
                {current.source.career_title ? `${current.source.career_title} · ` : ""}
                {current.source.version ? `version ${current.source.version} when captured` : "no version recorded"}
              </p>
            </Card>
          )}
          {current?.excerpt && (
            <Card className="stack-sm">
              <h2 className="section-title">Snapshot</h2>
              <p className="subtle">Copied on {formatDateTime(current.created_at)}. It doesn't change if the source does.</p>
              {current.excerpt_kind === "code"
                ? <CodeBlock code={current.excerpt} language="java" label="snapshot" />
                : <blockquote className="note-quote">{current.excerpt}</blockquote>}
            </Card>
          )}
          {current && (
            <Card className="stack-sm">
              <h2 className="section-title">Organize</h2>
              <span className="row">
                <Button size="sm" aria-pressed={current.pinned} onClick={() => void setFlags({ pinned: !current.pinned })} disabled={current.archived}>
                  {current.pinned ? "Unpin" : "Pin"}
                </Button>
                <Button size="sm" onClick={() => void setFlags({ archived: !current.archived })}>{current.archived ? "Unarchive" : "Archive"}</Button>
                <Button size="sm" variant="danger" loading={deleting} onClick={async () => {
                  setDeleting(true);
                  try {
                    await editor.save();
                    await api.deleteNote(current.id);
                    void qc.invalidateQueries({ queryKey: ["me", "notes"] });
                    navigate("/notes", { replace: true, state: { deleted: { id: current.id, title: current.title } } });
                  } catch (e) { setFlagError(e); setDeleting(false); }
                }}>Delete</Button>
              </span>
              <InlineError error={flagError} />
            </Card>
          )}
          {current && (
            <Card className="stack-sm" role="region" aria-label="Key points helper">
              <h2 className="section-title">Pull out key points</h2>
              <p className="subtle">Lists your own sentences that state an action or a lesson. No AI model is used, and nothing is saved unless you choose to.</p>
              {points ? (
                <div className="stack-sm">
                  {points.points.length === 0 ? <p>No action or lesson sentences found. Try “Next time I'll…” or a list.</p>
                    : <ul className="mini-list">{points.points.map((p) => <li key={p}>{p}</li>)}</ul>}
                  <span className="row">
                    {points.points.length > 0 && (
                      <Button size="sm" variant="primary" onClick={async () => {
                        try {
                          await editor.save();
                          const base = editor.server ?? current;
                          const n = await api.updateNote(current.id, { base_revision: base.revision, key_points: points.points });
                          editor.adopt(n);
                          qc.setQueryData(["me", "note", n.id], n);
                          setPoints(null);
                        } catch (e) { setPointsError(e); }
                      }}>Save these key points</Button>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => setPoints(null)}>Discard</Button>
                  </span>
                </div>
              ) : (
                <Button size="sm" onClick={async () => {
                  setPointsError(null);
                  await editor.save();
                  try { setPoints(await api.keyPoints(current.id)); } catch (e) { setPointsError(e); }
                }}>Suggest key points</Button>
              )}
              <InlineError error={pointsError} />
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}
