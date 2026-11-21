import type { ReactNode } from "react";

import { focusField } from "@/hooks/useFieldErrors";

/**
 * Field errors beside their controls, and a summary for longer forms (Volume 9, prompt 3). The
 * message is linked to its control with aria-describedby; aria-invalid marks the control. Text,
 * not only colour, says what's wrong and how to fix it.
 */
export function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return <span className="field__error" id={id}>{message}</span>;
}

/**
 * A labelled control with its error under it, for any control (input, select, textarea): the
 * same pattern as components/Field.tsx, which renders its own text input. The error stays outside
 * the <label>, so it isn't read as part of the control's name: the control names it with
 * aria-describedby (invalidProps, with `${id}-error`).
 */
export function ControlField({ id, label, error, children }: { id: string; label: ReactNode; error?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>{label}</label>
      {children}
      <FieldError id={`${id}-error`} message={error} />
    </div>
  );
}

/**
 * "Check 2 fields" with a link to each. Focus moves here after a refused save (tabIndex -1);
 * a link puts focus in its field.
 */
export function ErrorSummary({ id, items, other = [] }: {
  id: string;
  items: { fieldId: string; label: string; message: string }[];
  other?: string[];
}) {
  if (!items.length && !other.length) return null;
  const count = items.length;
  return (
    <div className="banner banner--danger stack-sm error-summary" id={id} tabIndex={-1} role="group" aria-labelledby={`${id}-title`}>
      <strong id={`${id}-title`}>
        {count ? `This wasn't saved. Check ${count === 1 ? "1 field" : `${count} fields`}:` : "This wasn't saved:"}
      </strong>
      <ul>
        {items.map((item) => (
          <li key={item.fieldId}>
            <a href={`#${item.fieldId}`} onClick={(e) => {
              e.preventDefault();
              focusField(item.fieldId); // reachable even inside a closed section or a group of choices
            }}>{item.label}</a>: {item.message}
          </li>
        ))}
        {other.map((message) => <li key={message}>{message}</li>)}
      </ul>
    </div>
  );
}
