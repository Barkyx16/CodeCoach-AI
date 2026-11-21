import { Link } from "react-router-dom";

import type { DisputeNote } from "@/api/types";

/**
 * Something derived from feedback the learner has disputed since (docs/DISPUTES.md): it stays where
 * it is, labelled, with the dispute one click away. The learner decides what to do with it.
 */
export function DisputedNote({ note, kept = false }: { note: DisputeNote | null | undefined; kept?: boolean }) {
  if (!note) return null;
  return (
    <p className="disputed-note">
      {note.text} <Link to={note.href}>See the dispute</Link>
      {kept && <span className="subtle"> It stays as it is; it's yours to keep, move or mark done.</span>}
    </p>
  );
}
