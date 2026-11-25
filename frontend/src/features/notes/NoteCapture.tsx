import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useNotes } from "@/api/queries";
import type { Note, NoteSource } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { useQueryClient } from "@tanstack/react-query";

import { NoteEditor } from "./NoteEditor";
import { useNoteAutosave } from "./useNoteAutosave";

/**
 * "Add a note" where the learner is practising. The note keeps a reference to this source and,
 * if chosen, a snapshot of its text; it's saved automatically once something is written.
 */
export function NoteCapture({ source, excerpt, excerptKind = "quote", excerptLabel }: {
  source: NoteSource;
  excerpt?: string | null;
  excerptKind?: "quote" | "code";
  excerptLabel?: string;
}) {
  const { user } = useAuth();
  const sourceKey = `${source.type}:${source.track ?? ""}:${source.id}${source.question_index != null ? `#q${source.question_index}` : ""}`;
  const draftKey = `note-capture:${user?.id ?? "anon"}:${sourceKey}`;
  const hasDraft = useMemo(() => {
    try { return Boolean(window.localStorage.getItem(draftKey)); } catch { return false; }
  }, [draftKey]);
  const [open, setOpen] = useState(hasDraft);
  const existing = useNotes({ source_type: source.type, source_id: source.question_index != null ? `${source.id}#q${source.question_index}` : source.id, status: "all", page_size: 5 }, Boolean(user));
  return (
    <section className="card stack-sm note-capture" aria-labelledby={`note-capture-${sourceKey}`}>
      <h2 className="section-title" id={`note-capture-${sourceKey}`}><Icon name="file" size={16} />Notes</h2>
      {existing.data && existing.data.total > 0 && (
        <ul className="mini-list">
          {existing.data.items.map((n) => <li key={n.id}><Link to={`/notes/${n.id}`}>{n.title}</Link> <span className="subtle">· {n.archived ? "archived" : "saved"}</span></li>)}
        </ul>
      )}
      {open ? <CaptureForm key={draftKey} source={source} draftKey={draftKey} excerpt={excerpt} excerptKind={excerptKind} excerptLabel={excerptLabel} onDone={() => setOpen(false)} />
        : <Button size="sm" onClick={() => setOpen(true)}>Add a note</Button>}
    </section>
  );
}

function CaptureForm({ source, draftKey, excerpt, excerptKind, excerptLabel, onDone }: {
  source: NoteSource;
  draftKey: string;
  excerpt?: string | null;
  excerptKind: "quote" | "code";
  excerptLabel?: string;
  onDone(): void;
}) {
  const qc = useQueryClient();
  const [withExcerpt, setWithExcerpt] = useState(Boolean(excerpt));
  const createWith = useMemo(
    () => ({ source, excerpt: withExcerpt && excerpt ? excerpt.slice(0, 4000) : null, excerpt_kind: withExcerpt && excerpt ? excerptKind : null }),
    [source, withExcerpt, excerpt, excerptKind],
  );
  const [saved, setSaved] = useState<Note | null>(null);
  const editor = useNoteAutosave({
    initial: null, createWith, draftKey,
    onSaved: (n) => { setSaved(n); void qc.invalidateQueries({ queryKey: ["me", "notes"] }); },
  });
  return (
    <div className="stack-sm">
      {excerpt && !saved && (
        <label className="learn-option">
          <input type="checkbox" checked={withExcerpt} onChange={(e) => setWithExcerpt(e.target.checked)} />
          Include a snapshot of {excerptLabel ?? "this text"} (a copy from now; it won't change if the original does)
        </label>
      )}
      <NoteEditor editor={editor} compact autoFocus />
      <span className="row">
        {saved && <Link to={`/notes/${saved.id}`}>Open in your notebook</Link>}
        <Button size="sm" variant="ghost" onClick={() => { void editor.save(); onDone(); }}>Close</Button>
      </span>
    </div>
  );
}
