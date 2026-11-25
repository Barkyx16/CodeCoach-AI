import { useId, useState } from "react";

/** A list typed one item per line: plain, keyboard-friendly and easy to paste into. */
export function ListField({ label, hint, value, onChange, max, maxLength }: {
  label: string; hint: string; value: string[]; onChange: (v: string[]) => void; max: number; maxLength: number;
}) {
  const [text, setText] = useState(value.join("\n"));
  const hintId = useId();
  const items = text.split("\n").map((l) => l.trim()).filter(Boolean);
  return (
    <label className="field"><span className="field__label">{label}</span>
      <span className="subtle" id={hintId}>{hint} {items.length > max ? `Only the first ${max} are kept.` : ""}</span>
      <textarea className="input" rows={3} aria-describedby={hintId} value={text}
        onChange={(e) => {
          setText(e.target.value);
          onChange(e.target.value.split("\n").map((l) => l.trim().slice(0, maxLength)).filter(Boolean).slice(0, max));
        }} />
    </label>
  );
}
