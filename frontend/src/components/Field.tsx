import { useId, type InputHTMLAttributes } from "react";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  optional?: boolean;
  hint?: string;
  error?: string | undefined;
}

/**
 * Accessible text input: the <label> holds only the label text, and the hint and error are
 * linked with aria-describedby, so screen readers announce "Password, edit text" followed by
 * the hint, instead of reading the hint as part of the field's name.
 */
export function Field({ label, optional, hint, error, id, ...input }: FieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  return (
    <div className="field">
      <label className="field__label" htmlFor={inputId}>
        {label}
        {optional && <span className="subtle"> (optional)</span>}
      </label>
      <input id={inputId} className="input" aria-invalid={error ? true : undefined}
        aria-describedby={[hintId, errorId].filter(Boolean).join(" ") || undefined} {...input} />
      {hint && <span className="field__hint" id={hintId}>{hint}</span>}
      {error && <span className="field__error" id={errorId}>{error}</span>}
    </div>
  );
}
