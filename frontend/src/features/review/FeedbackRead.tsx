import type { FeedbackRead } from "@/api/types";
import { formatDateTime } from "@/lib/format";

/**
 * What an interview's feedback read, recorded when it was scored (Volume 15, prompt 8;
 * docs/COACH_CONTEXT.md, "What the feedback read"): each part by its label and size, what was
 * replaced in it, who read it, and whether you checked it first. Never a copy of the text: the
 * transcript and your code are above, as you wrote them. When it changed after a check, each changed
 * part says how (Volume 17, prompt 1), and the lines added to your code are shown from that code.
 */
export function FeedbackReadSection({ read, code }: { read: FeedbackRead; code?: string | null }) {
  const changes = read.confirmed?.changes ?? [];
  const codeLines = (code ?? "").split("\n");
  return (
    <section className="card stack-sm feedback-read" aria-labelledby="feedback-read-title">
      <h2 className="section-title" id="feedback-read-title">What the feedback read</h2>
      <p className={read.recorded && read.checked === false ? "banner banner--info" : "subtle"}>
        {read.text}
        {read.confirmed && <> <span className="subtle">(checked <time dateTime={read.confirmed.at}>{formatDateTime(read.confirmed.at)}</time>)</span></>}
      </p>
      {changes.length > 0 && (
        <ul className="mini-list feedback-read__changes" aria-label="What changed after your check">
          {changes.map((c) => (
            <li key={c.label}>
              {c.text}.
              {/* The added lines, read from your code as it's kept (above), never from a copy. */}
              {code && (c.added_lines ?? []).length > 0 && (
                <pre className="feedback-read__lines" aria-label={`Lines added to ${c.label} after your check`}>
                  {(c.added_lines ?? []).filter((n) => n <= codeLines.length).map((n) => `${String(n).padStart(3)}  ${codeLines[n - 1]}`).join("\n")}
                </pre>
              )}
              {(c.added ?? 0) > (c.added_lines ?? []).length && (c.added_lines ?? []).length > 0 && (
                <span className="subtle"> The first {(c.added_lines ?? []).length} added lines are shown.</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {read.read_by && <p className="subtle">Read by: {read.read_by}.</p>}
      {(read.items ?? []).length > 0 && (
        <ul className="mini-list feedback-read__items">
          {(read.items ?? []).map((i) => (
            <li key={i.label}>
              <strong>{i.label}</strong> <span className="subtle">· {i.chars.toLocaleString()} characters{(i.notes ?? []).length ? ` · ${(i.notes ?? []).join(" ")}` : ""}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
