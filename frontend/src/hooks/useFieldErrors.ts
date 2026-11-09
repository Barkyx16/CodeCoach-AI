import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";

/**
 * Field errors from a rejected save (Volume 9, prompt 3; NAVIGATION.md "Field errors").
 *
 * The server's 422 says what was wrong with the values it was sent. So an error is shown beside
 * its field only while that field still holds the value that was rejected: edit it, and the old
 * error goes (the next save checks the new value). Errors the server didn't tie to one of the
 * form's fields stay in the form's own message. Anything that isn't a validation error (no
 * connection, no permission, a conflict) isn't a field error at all: the caller shows it as before.
 */
export type FieldMessages<K extends string> = Partial<Record<K, string>>;

export function validationMessages<K extends string>(error: unknown, fields: readonly K[]): { byField: FieldMessages<K>; other: string[] } | null {
  if (!(error instanceof ApiError) || error.code !== "validation_error" || !Array.isArray(error.details)) return null;
  const byField: FieldMessages<K> = {};
  const other: string[] = [];
  for (const item of error.details as { loc?: unknown[]; msg?: string; type?: string }[]) {
    const message = readable(item.type, item.msg ?? "This value isn't accepted.");
    const name = (item.loc ?? []).find((part): part is K => typeof part === "string" && (fields as readonly string[]).includes(part));
    if (name && !byField[name]) byField[name] = message;
    else if (!name) other.push(message);
  }
  return { byField, other };
}

/**
 * What's wrong and how to fix it, in words: the common kinds of refusal say what to do; anything
 * else is the server's own wording, made readable.
 */
export function readable(type: string | undefined, message: string): string {
  const limit = /at most (\d+)/.exec(message)?.[1];
  const least = /at least (\d+)/.exec(message)?.[1];
  switch (type) {
    case "missing":
      return "This is required: fill it in.";
    case "string_too_short":
      return least === "1" || !least ? "This can't be empty: fill it in." : `Use at least ${least} characters.`;
    case "string_too_long":
      return limit ? `Too long: use at most ${Number(limit).toLocaleString()} characters.` : "Too long: shorten it.";
    case "too_long":
      return limit ? `Too many: choose at most ${limit}.` : "Too many: choose fewer.";
    case "date_parsing":
    case "date_from_datetime_parsing":
    case "date_from_datetime_inexact":
    case "date_type":
      return "Not a date: choose a day, or leave it empty.";
    case "literal_error":
    case "enum":
      return "Not one of the choices: choose one from the list.";
    default:
      return plain(message);
  }
}

/** The server's wording, made readable: no "Value error," prefix, a full stop at the end. */
function plain(message: string): string {
  const m = message.replace(/^Value error, /, "").trim();
  const sentence = m.charAt(0).toUpperCase() + m.slice(1);
  return /[.!?]$/.test(sentence) ? sentence : `${sentence}.`;
}

/**
 * `form` is what the form holds now; `ids` says where each field is (for focus), and `summaryId`
 * names the form's summary when it has one.
 */
export function useFieldErrors<T extends object, K extends keyof T & string = keyof T & string>(
  fields: readonly K[],
  form: T,
  { ids, summaryId = null }: { ids: (name: K) => string; summaryId?: string | null },
) {
  const [state, setState] = useState<{ messages: FieldMessages<K>; other: string[]; sent: T } | null>(null);
  // What the form holds now, for a refusal that arrives later than the render that sent it.
  const latest = useRef(form);
  useEffect(() => { latest.current = form; }, [form]);

  /**
   * A save was refused: true when it was a validation error this hook now shows. Focus moves to
   * the summary (or the first field in error) only while the form still holds what was sent: a
   * refusal that arrives after the learner carried on typing doesn't pull them out of their field.
   */
  const rejected = useCallback((error: unknown, sent: T): boolean => {
    const parsed = validationMessages<K>(error, fields);
    if (!parsed) {
      setState(null);
      return false;
    }
    setState({ messages: parsed.byField, other: parsed.other, sent });
    if (JSON.stringify(latest.current) === JSON.stringify(sent)) {
      const first = fields.find((name) => parsed.byField[name]);
      focusAfterRejection(summaryId, first ? ids(first) : null);
    }
    return true;
  }, [fields, ids, summaryId]);
  const clear = useCallback(() => setState(null), []);

  /** The error for `name`, only while the field still holds the value that was refused. */
  const errorFor = (name: K): string | undefined => {
    if (!state) return undefined;
    const message = state.messages[name];
    return message && JSON.stringify(form[name]) === JSON.stringify(state.sent[name]) ? message : undefined;
  };
  /** The fields still in error, in the form's order. */
  const active: { name: K; message: string }[] = fields.flatMap((name) => {
    const message = errorFor(name);
    return message ? [{ name, message }] : [];
  });
  return { rejected, clear, errorFor, active, other: state?.other ?? [], shown: state !== null };
}

/**
 * Put focus in a field by id. A group of choices (a fieldset) can't take focus itself, so focus
 * goes to its first enabled control; a field inside a closed <details> section opens it first.
 */
export function focusField(id: string): boolean {
  const field = document.getElementById(id);
  if (!field) return false;
  field.closest("details")?.setAttribute("open", "");
  const control = field.matches("input, select, textarea, button, [tabindex]")
    ? field
    : field.querySelector<HTMLElement>("input:not([disabled]), select:not([disabled]), textarea:not([disabled])");
  (control ?? field).focus();
  return true;
}

/** After a refused save: focus the summary when there is one, else the first field in error. */
export function focusAfterRejection(summaryId: string | null, firstFieldId: string | null): void {
  window.setTimeout(() => {
    const summary = summaryId ? document.getElementById(summaryId) : null;
    if (summary) summary.focus();
    else if (firstFieldId) focusField(firstFieldId);
  }, 0);
}

/** Props for a control with an error: aria-invalid and the error's id in aria-describedby. */
export function invalidProps(errorId: string, message: string | undefined, describedBy?: string) {
  return {
    "aria-invalid": message ? true : undefined,
    "aria-describedby": [describedBy, message ? errorId : undefined].filter(Boolean).join(" ") || undefined,
  } as const;
}
