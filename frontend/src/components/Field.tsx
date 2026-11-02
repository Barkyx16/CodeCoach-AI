import { useId, useState, type InputHTMLAttributes, type ReactNode } from "react";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  optional?: boolean;
  hint?: string;
  error?: string | undefined;
  /** Extra content under the input (e.g. a live password checklist), linked like the hint. */
  extra?: ReactNode;
}

/**
 * Accessible text input: the <label> holds only the label text, and the hint and error are
 * linked with aria-describedby, so screen readers announce "Password, edit text" followed by
 * the hint, instead of reading the hint as part of the field's name.
 *
 * Password fields get a show/hide toggle (the eye button). It's a real <button> with a
 * pressed state, so keyboard and screen-reader users can use it too.
 */
export function Field({ label, optional, hint, error, extra, id, type, ...input }: FieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const extraId = extra ? `${inputId}-extra` : undefined;
  const isPassword = type === "password";
  const [visible, setVisible] = useState(false);
  const field = (
    <input id={inputId} className="input" type={isPassword && visible ? "text" : type}
      aria-invalid={error ? true : undefined}
      aria-describedby={[hintId, extraId, errorId].filter(Boolean).join(" ") || undefined} {...input} />
  );
  return (
    <div className="field">
      <label className="field__label" htmlFor={inputId}>
        {label}
        {optional && <span className="subtle"> (optional)</span>}
      </label>
      {isPassword ? (
        <div className="password-input">
          {field}
          <button type="button" className="password-input__toggle" aria-pressed={visible}
            aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
            title={visible ? "Hide password" : "Show password"} onClick={() => setVisible((v) => !v)}>
            <EyeIcon crossed={visible} />
          </button>
        </div>
      ) : field}
      {hint && <span className="field__hint" id={hintId}>{hint}</span>}
      {extra && <div id={extraId}>{extra}</div>}
      {error && <span className="field__error" id={errorId}>{error}</span>}
    </div>
  );
}

function EyeIcon({ crossed }: { crossed: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
      {crossed && <path d="M4 4l16 16" />}
    </svg>
  );
}
