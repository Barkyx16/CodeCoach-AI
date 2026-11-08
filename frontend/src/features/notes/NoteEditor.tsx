import { lazy, Suspense, useId, useState } from "react";
import { Link } from "react-router-dom";

import type { Note } from "@/api/types";
import { Button } from "@/components/Button";
import { CopyWork } from "@/components/CopyWork";
import { InlineError } from "@/components/States";
import { timeAgo } from "@/lib/format";

import { parseTags } from "./tags";
import type { NoteFields, SaveState, useNoteAutosave } from "./useNoteAutosave";

// The preview (and the markdown parser behind it) loads only when the learner switches to it.
const NoteMarkdown = lazy(() => import("./NoteMarkdown").then((m) => ({ default: m.NoteMarkdown })));

const STATUS: Record<SaveState, string> = {
  idle: "Not saved yet: start typing",
  unsaved: "Unsaved changes…",
  saving: "Saving…",
  saved: "Saved",
  error: "Could not save. Your text is kept in this browser.",
  conflict: "Not saved: this note changed somewhere else",
  pending: "Offline: saved on this device. Sync pending: it's sent when you're back online.",
  offline: "Not saved yet: you're offline. Kept on this device; press Save now when you're back online.",
};

// The text isn't on the server in these states. When this browser also couldn't keep a copy, the
// status says so plainly (and offers Copy), rather than claiming it's kept on this device.
const NOT_ON_SERVER = new Set<SaveState>(["unsaved", "error", "pending", "offline"]);
const NOT_KEPT: Partial<Record<SaveState, string>> = {
  unsaved: "Unsaved changes, and this browser can't keep a copy",
  error: "Could not save, and this browser can't keep a copy: copy your text",
  pending: "Offline, and this browser can't keep a copy: copy your text",
  offline: "Not saved: you're offline and this browser can't keep a copy: copy your text",
};

/** The editing surface shared by the capture panel and the note page. */
export function NoteEditor({ editor, compact = false, autoFocus = false }: {
  editor: ReturnType<typeof useNoteAutosave>;
  compact?: boolean;
  autoFocus?: boolean;
}) {
  const id = useId();
  const { fields, state, change } = editor;
  const [preview, setPreview] = useState(false);
  const [tagText, setTagText] = useState(fields.tags.join(", "));
  const [copy, setCopy] = useState<Note | null>(null);

  return (
    <div className="note-editor stack-sm">
      {editor.recovery && (
        <div className="banner banner--info stack-sm" role="region" aria-label="Unsaved draft found">
          <p>This browser has unsaved text for this note from {timeAgo(editor.recovery.at)}.</p>
          <span className="row">
            <Button size="sm" variant="primary" onClick={() => { editor.restore(); setTagText(editor.recovery?.fields.tags.join(", ") ?? ""); }}>Restore it</Button>
            <Button size="sm" variant="ghost" onClick={editor.discardRecovery}>Discard it</Button>
          </span>
        </div>
      )}
      {editor.conflict && <ConflictPanel editor={editor} mine={fields} saved={editor.conflict} onCopy={setCopy}
        onResolved={(f) => setTagText(f.tags.join(", "))} />}
      {copy && <p role="status" className="banner banner--success">Your version was saved as a separate note: <Link to={`/notes/${copy.id}`}>{copy.title}</Link>.</p>}

      <label className="field">
        <span className="field__label">Title</span>
        <input className="input" value={fields.title} maxLength={200} autoFocus={autoFocus}
          onChange={(e) => change({ title: e.target.value })} />
      </label>
      <div className="field">
        <div className="note-editor__bar">
          <span className="field__label" id={`${id}-body`}>Note</span>
          <span className="row note-editor__modes" role="group" aria-label="Note view">
            <button type="button" className="link-button" aria-pressed={!preview} onClick={() => setPreview(false)}>Write</button>
            <button type="button" className="link-button" aria-pressed={preview} onClick={() => setPreview(true)}>Preview</button>
          </span>
        </div>
        {preview ? <div className="note-preview" aria-labelledby={`${id}-body`}><Suspense fallback={<p className="subtle">Loading the preview…</p>}><NoteMarkdown text={fields.body} /></Suspense></div> : (
          <textarea className="input note-editor__body" rows={compact ? 5 : 12} maxLength={20000} value={fields.body}
            aria-labelledby={`${id}-body`} aria-describedby={`${id}-md`} onChange={(e) => change({ body: e.target.value })} />
        )}
        <span className="subtle note-editor__hint" id={`${id}-md`}>Plain text or Markdown (**bold**, lists, `code`). HTML isn't rendered.</span>
      </div>
      <label className="field">
        <span className="field__label">Tags <span className="subtle">(comma-separated)</span></span>
        <input className="input" value={tagText} placeholder="e.g. sbar, escalation"
          onChange={(e) => { setTagText(e.target.value); change({ tags: parseTags(e.target.value) }); }} />
      </label>
      <label className="field">
        <span className="field__label">Private reflection <span className="subtle">(optional)</span></span>
        <textarea className="input" rows={compact ? 2 : 4} maxLength={5000} value={fields.reflection}
          placeholder="What would you do differently next time?" onChange={(e) => change({ reflection: e.target.value })} />
      </label>
      <div className="row note-editor__status">
        {/* Not a live region (it changes as you type); failures and conflicts are announced by their own alerts. */}
        <span className={`note-status note-status--${state}`}>{editor.kept || !NOT_ON_SERVER.has(state) ? STATUS[state] : NOT_KEPT[state]}</span>
        {!editor.kept && NOT_ON_SERVER.has(state) && <CopyWork text={[fields.title, fields.body].filter(Boolean).join("\n\n")} />}
        {state === "conflict" && <span className="visually-hidden" role="alert">Not saved: this note changed somewhere else. Choose which version to keep.</span>}
        {state === "error" && <Button size="sm" onClick={() => void editor.save()}>Try again</Button>}
        {(state === "unsaved" || state === "offline") && <Button size="sm" variant="ghost" onClick={() => void editor.save()}>Save now</Button>}
        {state === "pending" && <Button size="sm" variant="ghost" onClick={() => void editor.save()}>Try now</Button>}
      </div>
      {state === "error" && <InlineError error={editor.error} />}
    </div>
  );
}

function ConflictPanel({ editor, mine, saved, onResolved, onCopy }: {
  editor: ReturnType<typeof useNoteAutosave>;
  mine: NoteFields;
  saved: Note;
  onResolved(f: NoteFields): void;
  onCopy(n: Note): void;
}) {
  return (
    <section className="banner banner--warning stack-sm note-conflict" role="region" aria-label="Edit conflict">
      <strong>This note was changed in another tab or device ({timeAgo(saved.updated_at)}).</strong>
      <p>Nothing has been overwritten. Compare the two versions and choose what to keep.</p>
      <div className="note-conflict__versions">
        <div>
          <h3 className="learn-subtitle">Your version (not saved)</h3>
          <p className="note-conflict__title">{mine.title || "Untitled note"}</p>
          <pre className="note-conflict__text">{mine.body || "(empty)"}</pre>
        </div>
        <div>
          <h3 className="learn-subtitle">Saved version</h3>
          <p className="note-conflict__title">{saved.title}</p>
          <pre className="note-conflict__text">{saved.body || "(empty)"}</pre>
        </div>
      </div>
      <span className="row">
        <Button size="sm" variant="primary" onClick={() => editor.keepMine()}>Keep my version</Button>
        <Button size="sm" onClick={() => { editor.takeSaved(); onResolved({ title: saved.title, body: saved.body, reflection: saved.reflection, tags: saved.tags }); }}>Use the saved version</Button>
        <Button size="sm" variant="ghost" onClick={async () => {
          const c = await editor.saveMineAsNew();
          if (c) { onCopy(c); onResolved({ title: saved.title, body: saved.body, reflection: saved.reflection, tags: saved.tags }); }
        }}>Keep both</Button>
      </span>
    </section>
  );
}
