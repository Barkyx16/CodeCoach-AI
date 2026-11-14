import type { AttemptConditions } from "@/api/types";
import { formatDay } from "@/features/applications/dates";
import { formatDateTime } from "@/lib/format";

/**
 * The conditions of a practice attempt (docs/ATTEMPT_CONDITIONS.md): the in-app help shown for this
 * question and version since the previous attempt. Only the four labels the server gives; it never
 * claims anything about help outside the app, and it changes no score or verdict.
 */
export function AttemptConditionsView({ conditions }: { conditions: AttemptConditions | null | undefined }) {
  if (!conditions) return null;
  const notRecorded = conditions.labels.includes("Not recorded");
  return (
    <div className="attempt-conditions stack-sm">
      <p>
        <strong>In-app help before this attempt:</strong> {conditions.labels.join(", ")}
        {notRecorded && <span className="subtle"> (help is recorded from {formatDay(conditions.recorded_from)})</span>}
      </p>
      {conditions.help.length > 0 && (
        <ul className="mini-list">
          {conditions.help.map((h) => (
            <li key={`${h.at}-${h.detail}`}>
              {h.label}: {h.detail}, <time dateTime={h.at}>{formatDateTime(h.at)}</time>
            </li>
          ))}
        </ul>
      )}
      <p className="subtle">{conditions.note} It doesn't change the score or the verdict.</p>
    </div>
  );
}
