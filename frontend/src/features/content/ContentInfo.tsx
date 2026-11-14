import type { ContentKind, ContentMeta } from "@/api/types";
import { useContentMeta } from "@/api/queries";
import { formatDateTime, titleCase } from "@/lib/format";

/**
 * What a learner should know about a question or problem: career, topic, level, version, how it
 * was made and what has (or hasn't) been checked, and any published corrections. Labels come
 * from the server's recorded evidence; none is assumed here.
 */
export function ContentInfo({ type, id, seenVersion, seenWhat = "answered" }: {
  type: ContentKind; id: string;
  /** The version the learner last answered or saved, to point out what changed since. */
  seenVersion?: number | null;
  seenWhat?: "answered" | "saved";
}) {
  const meta = useContentMeta(type, id);
  if (!meta.data) return null;
  const m = meta.data;
  return (
    <>
      <ChangedSince meta={m} seenVersion={seenVersion} seenWhat={seenWhat} />
      <details className="content-info">
        <summary>
          About this {type === "question" ? "question" : "problem"} · {m.version_label}
          {m.changes.length > 0 ? ` · corrected ${m.changes.length === 1 ? "once" : `${m.changes.length} times`}` : ""}
        </summary>
        <dl className="content-info__facts">
          {m.career && <div><dt>Career</dt><dd>{m.career}</dd></div>}
          {m.topic && <div><dt>Topic</dt><dd>{m.topic}</dd></div>}
          {m.level && <div><dt>Level</dt><dd>{titleCase(m.level)}</dd></div>}
          <div><dt>Version</dt><dd>{m.version_label}</dd></div>
        </dl>
        <ul className="content-info__labels">
          {m.labels.map((l) => <li key={l.key} className={`content-label content-label--${l.key}`}>{l.text}</li>)}
        </ul>
        {m.changes.length > 0 && (
          <div className="stack-sm">
            <h3 className="content-info__sub">What changed</h3>
            <ol className="content-info__changes">
              {m.changes.map((c) => <li key={c.version} value={c.version}>Version {c.version} ({formatDateTime(c.at)}): {c.note}</li>)}
            </ol>
          </div>
        )}
      </details>
    </>
  );
}

function ChangedSince({ meta, seenVersion, seenWhat }: { meta: ContentMeta; seenVersion?: number | null; seenWhat: string }) {
  if (meta.status === "retired") {
    return (
      <p className="banner banner--warning" role="status">
        <strong>Retired.</strong> {meta.retired_reason} It isn't used for practice or assessment any more; your earlier work on it is kept.
      </p>
    );
  }
  if (!seenVersion || seenVersion >= meta.version) return null;
  const since = meta.changes.filter((c) => c.version > seenVersion && c.significant);
  if (since.length === 0) return null;
  return (
    <div className="banner banner--info" role="status">
      <strong>This {meta.content_type} changed since you {seenWhat} it</strong> (version {seenVersion} → {meta.version}).
      <ul className="mini-list">{since.map((c) => <li key={c.version}>{c.note}</li>)}</ul>
    </div>
  );
}
