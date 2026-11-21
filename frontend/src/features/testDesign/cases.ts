import type { TestCaseIn, TestDesignExercise } from "@/api/types";

/** A case as the form holds it: every field as typed, so nothing half-typed is lost. */
export interface CaseRow {
  id: string;
  fields: Record<string, string>;
  expected: string;
  label: "" | NonNullable<TestCaseIn["label"]>;
  note: string;
}

export const LABELS: { value: CaseRow["label"]; text: string }[] = [
  { value: "", text: "Not labelled" },
  { value: "boundary", text: "Boundary" },
  { value: "equivalence", text: "Equivalence class" },
  { value: "edge", text: "Edge condition" },
  { value: "other", text: "Other" },
];

export const newRow = (ex: TestDesignExercise): CaseRow => ({
  id: `c${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
  fields: Object.fromEntries(ex.params.map((p) => [p.name, ""])),
  expected: ex.returns === "boolean" ? "true" : "",
  label: "",
  note: "",
});

const WHOLE = /^-?\d+$/;

/** The case to send, or plain messages per field. The server checks the same rules again. */
export function parseRow(ex: TestDesignExercise, row: CaseRow): { case: TestCaseIn } | { errors: Record<string, string> } {
  const { min_value: lo, max_value: hi, max_length: maxLen } = ex.limits;
  const errors: Record<string, string> = {};
  const input: Record<string, unknown> = {};
  for (const p of ex.params) {
    const raw = (row.fields[p.name] ?? "").trim();
    if (p.type === "int[]") {
      const parts = raw === "" ? [] : raw.split(/[\s,]+/).filter(Boolean);
      if (!parts.every((x) => WHOLE.test(x))) { errors[p.name] = "Whole numbers separated by commas, like 3, -1, 7."; continue; }
      const values = parts.map(Number);
      if (values.length > maxLen) errors[p.name] = `At most ${maxLen} values (this has ${values.length}).`;
      else if (values.some((v) => v < lo || v > hi)) errors[p.name] = `Each value between ${lo} and ${hi}.`;
      else input[p.name] = values;
    } else if (!WHOLE.test(raw)) {
      errors[p.name] = raw ? "A whole number." : "Give a value.";
    } else if (Number(raw) < lo || Number(raw) > hi) {
      errors[p.name] = `Between ${lo} and ${hi}.`;
    } else {
      input[p.name] = Number(raw);
    }
  }
  let expected: number | boolean | undefined;
  if (ex.returns === "boolean") expected = row.expected === "true";
  else if (WHOLE.test(row.expected.trim())) expected = Number(row.expected.trim());
  else errors.expected = row.expected.trim() ? "A whole number." : "Give the output the specification calls for.";
  if (Object.keys(errors).length) return { errors };
  return { case: { input, expected, label: row.label || null, note: row.note.trim() } };
}

/** A sent case back into the form (to revise an earlier run as a new attempt). */
export function rowFrom(ex: TestDesignExercise, c: { input: Record<string, unknown>; expected: unknown; label?: string | null; note?: string }): CaseRow {
  return {
    ...newRow(ex),
    fields: Object.fromEntries(ex.params.map((p) => {
      const v = c.input[p.name];
      return [p.name, Array.isArray(v) ? v.join(", ") : v == null ? "" : String(v)];
    })),
    expected: String(c.expected),
    label: (c.label ?? "") as CaseRow["label"],
    note: c.note ?? "",
  };
}

export const signatureText = (ex: TestDesignExercise) =>
  `${ex.returns} ${ex.method}(${ex.params.map((p) => `${p.type} ${p.name}`).join(", ")})`;

export const draftKey = (userId: string, slug: string) => `test-design-draft:${userId}:${slug}`;
