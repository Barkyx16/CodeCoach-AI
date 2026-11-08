import { Button } from "./Button";

/** One part of a record, as this page has it and as the server saved it. */
export interface ConflictField {
  label: string;
  mine: string;
  saved: string;
}

/**
 * A save refused because the record was saved elsewhere since this page loaded it (409
 * stale_revision with the saved version in `details.current`). Nothing was overwritten: the
 * learner sees both versions (the parts that differ), copies theirs if they like, and chooses
 * which to keep. Nothing is merged automatically.
 */
export function VersionConflict({ what, savedWhen, fields, busy = false, keepMineLabel = "Keep my version", onKeepMine, onUseSaved }: {
  /** "story", "reflection", "diagram", "kit" */
  what: string;
  /** e.g. "version 3, 2 minutes ago" */
  savedWhen: string;
  fields: ConflictField[];
  busy?: boolean;
  keepMineLabel?: string;
  onKeepMine(): void;
  onUseSaved(): void;
}) {
  const differing = fields.filter((f) => f.mine !== f.saved);
  const shown = differing.length ? differing : fields;
  const mineText = fields.map((f) => `${f.label}:\n${f.mine}`).join("\n\n");
  const show = (text: string) => text.trim() || "(empty)";
  return (
    <section className="banner banner--warning stack-sm version-conflict" role="region" aria-label="Edit conflict">
      {/* Announced once when it appears: a save the learner just asked for didn't happen. */}
      <p role="alert"><strong>This {what} was saved in another tab or on another device ({savedWhen}).</strong></p>
      <p>
        Nothing has been overwritten, and your version is still on this page. Compare them and choose which to keep.
        {differing.length > 0 && differing.length < fields.length ? ` Only the parts that differ are shown (${differing.length} of ${fields.length}).` : ""}
      </p>
      <div className="version-conflict__versions">
        <div>
          <h3 className="learn-subtitle">Your version (not saved)</h3>
          {shown.map((f) => (
            <div key={f.label} className="version-conflict__field">
              <p className="version-conflict__label">{f.label}</p>
              <pre className="version-conflict__text">{show(f.mine)}</pre>
            </div>
          ))}
        </div>
        <div>
          <h3 className="learn-subtitle">Saved version</h3>
          {shown.map((f) => (
            <div key={f.label} className="version-conflict__field">
              <p className="version-conflict__label">{f.label}</p>
              <pre className="version-conflict__text">{show(f.saved)}</pre>
            </div>
          ))}
        </div>
      </div>
      <span className="row">
        <Button size="sm" variant="primary" loading={busy} onClick={onKeepMine}>{keepMineLabel}</Button>
        <Button size="sm" disabled={busy} onClick={onUseSaved}>Use the saved version</Button>
        <Button size="sm" variant="ghost" onClick={() => void navigator.clipboard?.writeText(mineText).catch(() => undefined)}>Copy my version</Button>
      </span>
    </section>
  );
}
