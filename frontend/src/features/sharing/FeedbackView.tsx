import type { ReactNode } from "react";

import type { ShareFeedback } from "@/api/types";
import { formatDateTime } from "@/lib/format";

const SECTIONS = [
  ["clear", "What was clear?"],
  ["needs_evidence", "What needs more evidence?"],
  ["next_step", "One useful next step"],
] as const;

/** One person's feedback. Everything is rendered as plain text (never HTML). */
export function FeedbackView({ item, actions }: { item: ShareFeedback; actions?: ReactNode }) {
  return (
    <article className="card stack-sm share-feedback" aria-label={`Feedback from ${item.reviewer.label}`}>
      <header className="share-feedback__head">
        <p><strong>{item.reviewer.label}</strong> <span className="subtle">· {formatDateTime(item.created_at)}</span></p>
        {item.useful && <span className="badge badge--success">Marked useful</span>}
      </header>
      <dl className="share-feedback__answers">
        {SECTIONS.filter(([key]) => item[key]).map(([key, label]) => (
          <div key={key}>
            <dt>{label}</dt>
            <dd>{item[key]}</dd>
          </div>
        ))}
      </dl>
      {item.comments.length > 0 && (
        <div className="stack-sm">
          <h3 className="share-feedback__sub">Comments on sentences</h3>
          <ul className="share-comments">
            {item.comments.map((c, i) => (
              <li key={i}>
                <blockquote className="share-comments__quote"><span className="subtle">Sentence {c.sentence + 1}:</span> {c.quote}</blockquote>
                <p>{c.text}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
      {actions}
    </article>
  );
}
