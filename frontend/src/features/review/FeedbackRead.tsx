import type { FeedbackRead } from "@/api/types";

/**
 * What an interview's feedback read, recorded when it was scored (Volume 15, prompt 8;
 * docs/COACH_CONTEXT.md, "What the feedback read"): each part by its label and size, what was
 * replaced in it, who read it, and whether you checked it first. Never a copy of the text: the
 * transcript and your code are above, as you wrote them.
 */
export function FeedbackReadSection({ read }: { read: FeedbackRead }) {
  return (
    <section className="card stack-sm feedback-read" aria-labelledby="feedback-read-title">
      <h2 className="section-title" id="feedback-read-title">What the feedback read</h2>
      <p className={read.recorded && read.checked === false ? "banner banner--info" : "subtle"}>{read.text}</p>
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
