import { useInterviewFormats } from "@/api/queries";
import type { Difficulty, InterviewFormatId } from "@/api/types";
import { LoadingState } from "@/components/States";

/** Choose an interview format. Unavailable formats stay visible with the reason; nothing is hidden silently. */
export function FormatPicker({ track, level, value, onChange }: {
  track: string;
  level: Difficulty;
  value: InterviewFormatId;
  onChange(v: InterviewFormatId): void;
}) {
  const formats = useInterviewFormats(track, level);
  if (formats.isPending) return <LoadingState label="Loading formats…" />;
  if (formats.isError) return <p className="subtle">Formats couldn't be loaded; the standard mixed interview is used.</p>;
  const chosen = formats.data.find((f) => f.id === value) ?? formats.data[0]!;
  return (
    <div className="stack-sm">
      <fieldset className="field format-picker">
        <legend className="field__label">Format</legend>
        {formats.data.map((f) => (
          <label key={f.id} className={`format-option${f.available ? "" : " format-option--off"}${value === f.id ? " format-option--active" : ""}`}>
            <input type="radio" name="format" value={f.id} checked={value === f.id} disabled={!f.available}
              aria-describedby={`format-${f.id}-why`} onChange={() => onChange(f.id)} />
            <span className="format-option__text">
              <strong>{f.title}</strong>
              <span className="subtle" id={`format-${f.id}-why`}>{f.available ? f.practices : `Not available: ${f.unavailable_reason}`}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <section className="format-preview" aria-labelledby="format-preview-title">
        <h3 className="learn-subtitle" id="format-preview-title">What to expect: {chosen.title}</h3>
        <ol className="mini-list mini-list--numbered">
          {chosen.structure.map((slot) => (
            <li key={slot.position}>
              {slot.speaker ? <><strong>{slot.speaker.title}</strong> asks: </> : null}{slot.kind_label}
            </li>
          ))}
        </ol>
        {chosen.roles.length > 0 && (
          <p className="subtle">
            A simulated panel: these are generic roles, not a real employer or real people. One speaks at a time and each has its own focus
            ({chosen.roles.map((r) => `${r.title.toLowerCase()}: ${r.objective.toLowerCase()}`).join("; ")}).
          </p>
        )}
        <p className="subtle">
          {chosen.follow_ups > 0
            ? `Up to ${chosen.follow_ups} short follow-up questions, chosen from what your answers leave out. You can answer or skip them.`
            : "No follow-up questions."}
        </p>
      </section>
    </div>
  );
}
