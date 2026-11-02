import { ApiError } from "@/api/client";

export type FieldErrors = Partial<Record<"email" | "password" | "display_name" | "new_password", string>>;

/** Map the backend's 422 `details` (loc/msg) onto form fields. */
export function fieldErrorsFrom(error: unknown): FieldErrors {
  if (!(error instanceof ApiError)) return {};
  if (error.code === "email_taken") return { email: error.message };
  if (error.code !== "validation_error" || !Array.isArray(error.details)) return {};
  const out: FieldErrors = {};
  for (const item of error.details as { loc?: unknown[]; msg?: string }[]) {
    const field = item.loc?.[item.loc.length - 1];
    if (field === "email" || field === "password" || field === "display_name" || field === "new_password") {
      out[field] = (item.msg ?? "Invalid value").replace(/^Value error, /, "");
    }
  }
  return out;
}
