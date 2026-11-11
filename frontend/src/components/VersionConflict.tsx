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
export function VersionConflict({ what, savedWhen, fields, busy = false, keepMineLabel = "Keep my version", earlierSave, level = 3, onKeepMine, onUseSaved }: {
  /** "story", "reflection", "diagram", "kit" */
  what: string;
  /** Set when this page's own save went through (as this version) and its reply was lost, and
   * the record was changed after that (Volume 8, prompt 3): said, instead of "not saved". */
  earlierSave?: number | null;
  /** e.g. "version 3, 2 minutes ago" */
  savedWhen: string;
  fields: ConflictField[];
  busy?: boolean;
  keepMineLabel?: string;
  /** The heading level that fits where it's shown (the page's outline mustn't skip a level). */
  level?: 2 | 3;
  onKeepMine(): void;
  onUseSaved(): void;
}) {
  const differing = fields.filter((f) => f.mine !== f.saved);
  const shown = differing.length ? differing : fields;
  const mineText = fields.map((f) => `${f.label}:\n${f.mine}`).join("\n\n");
  const show = (text: string) => text.trim() || "(empty)";
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <section className="banner banner--warning stack-sm version-conflict" role="region" aria-label="Edit conflict">
      {/* Announced once when it appears: a save the learner just asked for didn't happen. */}
      {earlierSave ? (
        <p role="alert"><strong>Your save went through as version {earlierSave}. This {what} was changed after that, in another
          tab or on another device ({savedWhen}).</strong></p>
      ) : (
        <p role="alert"><strong>This {what} was saved in another tab or on another device ({savedWhen}).</strong></p>
      )}
      <p>
        Nothing has been overwritten, and your version is still on this page. Compare them and choose which to keep.
        {differing.length > 0 && differing.length < fields.length ? ` Only the parts that differ are shown (${differing.length} of ${fields.length}).` : ""}
      </p>
      <div className="version-conflict__versions">
        <div>
          <Heading className="learn-subtitle">{earlierSave ? `Your version (saved as version ${earlierSave}, then changed)` : "Your version (not saved)"}</Heading>
          {shown.map((f) => (
            <div key={f.label} className="version-conflict__field">
              <p className="version-conflict__label">{f.label}</p>
              <pre className="version-conflict__text">{show(f.mine)}</pre>
            </div>
          ))}
        </div>
        <div>
          <Heading className="learn-subtitle">{earlierSave ? "The newer saved version" : "Saved version"}</Heading>
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
