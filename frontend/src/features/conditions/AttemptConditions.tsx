import type { AttemptConditions } from "@/api/types";
import { formatDay } from "@/features/applications/dates";
import { formatDateTime } from "@/lib/format";

/**
 * The conditions of a practice attempt (docs/ATTEMPT_CONDITIONS.md): the in-app help shown for this
 * question and version since the previous attempt. Only the four labels the server gives; it never
 * claims anything about help outside the app, and it changes no score or verdict.
 */
export function AttemptConditionsView({ conditions, noun = "attempt", brief = false }: {
  conditions: AttemptConditions | null | undefined;
  /** "answer" for an answer given in an interview round; "interview" for a coding interview. */
  noun?: "attempt" | "answer" | "interview";
  /** One line (a round's results): the labels and the format, without the details. */
  brief?: boolean;
}) {
  if (!conditions) return null;
  const notRecorded = conditions.labels.includes("Not recorded");
  const round = conditions.round ?? null;
  const interview = conditions.interview ?? null;
  const line = (
    <p>
      <strong>In-app help before this {noun}:</strong> {conditions.labels.join(", ")}
      {notRecorded && (
        <span className="subtle"> ({round ? "for interview rounds, help" : "help"} is recorded from {formatDay(conditions.recorded_from)})</span>
      )}
    </p>
  );
  if (brief) {
    return (
      <div className="attempt-conditions attempt-conditions--brief">
        {line}
        {round && <p className="subtle">{round.text}</p>}
      </div>
    );
  }
  return (
    <div className="attempt-conditions stack-sm">
      {line}
      {round && <p><strong>How it was given:</strong> {round.text} <span className="subtle">(the format, not help)</span></p>}
      {interview && <p><strong>How it was given:</strong> {interview.text} <span className="subtle">(the format, not help)</span></p>}
      {conditions.unrecorded && <p className="subtle">{conditions.unrecorded}</p>}
      {conditions.help.length > 0 && (
        <ul className="mini-list">
          {conditions.help.map((h) => (
            <li key={`${h.at}-${h.detail}`}>
              {h.label}: {h.detail}, <time dateTime={h.at}>{formatDateTime(h.at)}</time>
            </li>
          ))}
        </ul>
      )}
      {interview && interview.checks.length > 0 && (
        <ul className="mini-list" aria-label="Checked before it left CodeCoach">
          {interview.checks.map((c) => (
            <li key={`${c.at}-${c.what}`}>
              {c.what}: {c.detail}, <time dateTime={c.at}>{formatDateTime(c.at)}</time>
            </li>
          ))}
        </ul>
      )}
      <p className="subtle">{conditions.note} It doesn't change the score or the verdict.</p>
    </div>
  );
}
