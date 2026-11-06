import type { Kit } from "@/api/types";
import { describeWhen } from "@/features/applications/dates";

import { FORMAT_LABEL, type PrintChoice } from "./labels";

/**
 * The printable pack: shown on screen as the preview and the only thing that prints, so the two
 * can't differ. Only what the learner chose is in it; private details are off unless chosen.
 * With unsaved changes it prints only a notice (even from the browser's own Print), so an unsaved
 * kit is never printed as if it were the saved one.
 */
export function PrintPack({ kit, choice, unsaved = false }: { kit: Kit; choice: PrintChoice; unsaved?: boolean }) {
  const remaining = kit.checklist.filter((c) => !c.done && !c.hidden);
  const asking = kit.questions.filter((q) => !q.excluded);
  return (
    <article className={`print-pack${unsaved ? " print-pack--unsaved" : ""}`} aria-label="Your interview pack">
      {unsaved && (
        <p className="print-pack__unsaved">
          This kit has unsaved changes, so it isn't printed. Save the kit, then print it.
        </p>
      )}
      <header>
        <h2>{kit.event_title}: {kit.role_title}, {kit.employer}</h2>
        <p className="print-pack__note">Your own preparation notes. Not sent to anyone.</p>
      </header>
      {choice.when && <p><strong>When:</strong> {describeWhen(kit)} · {FORMAT_LABEL[kit.format]}</p>}
      {choice.location && kit.location && <p><strong>Where:</strong> {kit.location}</p>}
      {choice.meetingLink && kit.meeting_link && <p><strong>Link:</strong> {kit.meeting_link}</p>}
      {choice.interviewers && kit.interviewers.some((p) => p.name || p.role) && (
        <section><h3>Interviewers</h3><ul>{kit.interviewers.filter((p) => p.name || p.role).map((p, i) => <li key={i}>{[p.name, p.role].filter(Boolean).join(", ")}</li>)}</ul></section>
      )}
      {choice.stories && kit.stories.length > 0 && (
        <section><h3>Examples</h3><ul>{kit.stories.map((s) => <li key={s.id}><strong>{s.title}</strong>{s.short_version ? `: ${s.short_version}` : ""}</li>)}</ul></section>
      )}
      {choice.questions && asking.length > 0 && <section><h3>Questions to ask</h3><ol>{asking.map((q) => <li key={q.id}>{q.text}</li>)}</ol></section>}
      {choice.checklist && remaining.length > 0 && <section><h3>Still to do</h3><ul>{remaining.map((c) => <li key={c.id}>☐ {c.text}</li>)}</ul></section>}
      {choice.notes && kit.notes && <section><h3>Notes</h3><p className="print-pack__notes">{kit.notes}</p></section>}
    </article>
  );
}
