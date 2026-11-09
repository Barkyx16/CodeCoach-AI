import { COPY_PREFIXES, localWorkKeys } from "@/auth/localWork";
import { readCopy } from "@/lib/deviceCopies";

/**
 * What each kind of copy on this device is, for "Your data" (docs/YOUR_DATA.md): its label, what
 * stays on the account when it's removed, and its page. Keyed by the ids in auth/localWork.ts
 * COPY_PREFIXES; a test checks every prefix has one.
 */
export interface CopyKindDetails {
  label: string;
  /** What stays on the account when this copy is removed. */
  keeps: string;
  /** "none": this text exists only here (never sent); "saved": unsaved changes to something saved. */
  onAccount: "none" | "saved";
  /** The page it belongs to, from the rest of the key; null when there isn't one to open. */
  open?: (rest: string) => string | null;
  /** Counted in lines (code), not words. */
  code?: boolean;
}

export type CopyKind = CopyKindDetails & (typeof COPY_PREFIXES)[number];

const NOT_SENT = "Nothing: it was never sent, so removing it deletes this text.";
const LAST_SAVED = "Your account keeps the last version you saved.";
const head = (rest: string, sep: string) => rest.split(sep)[0] ?? "";
const at = (path: string, id: string) => (id && id !== "new" ? `${path}/${encodeURIComponent(id)}` : path);

export const KIND_DETAILS: Record<string, CopyKindDetails> = {
  "answer": { onAccount: "none", label: "Written answer, not sent", keeps: NOT_SENT,
    open: (r) => { const [track, q] = r.split("."); return track && q ? `/careers/${encodeURIComponent(track)}/questions/${encodeURIComponent(q)}` : null; } },
  "code": { onAccount: "none", label: "Code, not submitted", code: true,
    keeps: "Your account keeps the code you submitted; this newer code goes.",
    open: (r) => (r.startsWith("interview-") ? null : at("/problems", r)) },
  "note": { onAccount: "saved", label: "Note changes, not saved yet", keeps: `${LAST_SAVED} A new note that was never saved is gone.`, open: (r) => at("/notes", r) },
  "note-capture": { onAccount: "none", label: "Quick note, not saved yet", keeps: NOT_SENT },
  "learn": { onAccount: "none", label: "Lesson exercise answer, not sent", keeps: NOT_SENT, open: (r) => at("/learn", r) },
  "story": { onAccount: "saved", label: "Story changes, not saved yet", keeps: `${LAST_SAVED} A new story that was never saved is gone.`, open: (r) => (r === "new" ? "/stories/new" : at("/stories", r)) },
  "whiteboard": { onAccount: "saved", label: "Diagram changes, not saved yet", keeps: LAST_SAVED, open: (r) => at("/whiteboard", r) },
  "reflection": { onAccount: "saved", label: "Interview reflection changes, not saved yet", keeps: LAST_SAVED },
  "drill": { onAccount: "none", label: "Drill answer, not sent", keeps: NOT_SENT, open: (r) => at("/drills", r) },
  "form": { onAccount: "saved", label: "Unfinished form", keeps: LAST_SAVED,
    open: (r) => (head(r, ":") === "application" ? at("/applications", r.split(":")[1] ?? "") : null) },
  "debug-notes": { onAccount: "none", label: "Debugging-lab notes (kept only on this device)",
    keeps: "Nothing: these notes are never sent, so removing them deletes them.", open: (r) => at("/problems", r) },
  "code-review": { onAccount: "saved", label: "Code review changes, not saved yet", keeps: LAST_SAVED, open: (r) => at("/code-reviews", r) },
  "test-design": { onAccount: "none", label: "Test cases, not run yet", keeps: "Your account keeps the runs you sent; these cases go.", open: (r) => at("/test-design", r) },
  "work-sample": { onAccount: "saved", label: "Work sample changes, not saved yet", keeps: LAST_SAVED, open: (r) => at("/work-samples", r) },
  "compare": { onAccount: "none", label: "Sample-answer marks, not sent", keeps: NOT_SENT, open: (r) => at("/compare", head(r, ":")) },
  "queue": { onAccount: "none", label: "Work-queue order and reasons, not sent", keeps: NOT_SENT, open: (r) => at("/scenarios/attempts", head(r, ":")) },
  "offer-rehearsal": { onAccount: "none", label: "Offer rehearsal turn, not sent", keeps: NOT_SENT, open: (r) => at("/offers/rehearsals", head(r, ":")) },
  "offer-compare": { onAccount: "saved", label: "Offer comparison changes, not saved yet", keeps: LAST_SAVED, open: (r) => at("/offers/compare", r) },
  "application-notes": { onAccount: "saved", label: "Application notes, not saved yet", keeps: LAST_SAVED, open: (r) => at("/applications", r) },
  "round": { onAccount: "none", label: "Interview answer, not sent", keeps: NOT_SENT, open: (r) => at("/interviews", head(r, ".")) },
  "interview-message": { onAccount: "none", label: "Interview message, not sent", keeps: NOT_SENT, open: (r) => at("/interviews", r) },
  "retry": { onAccount: "none", label: "Interview retry answer, not sent", keeps: NOT_SENT,
    open: (r) => { const [iv, i] = r.split("."); return iv && i ? `/interviews/${encodeURIComponent(iv)}/retry/${encodeURIComponent(i)}` : null; } },
};

const KINDS: CopyKind[] = COPY_PREFIXES.flatMap((p) => (KIND_DETAILS[p.id] ? [{ ...KIND_DETAILS[p.id]!, ...p }] : []));

/** One copy on this device, described without its content: what it is, how big, where it opens. */
export interface DeviceCopy {
  key: string;
  kind: CopyKind;
  /** Words of text (lines, for code). */
  size: number;
  /** When it was last kept, if the copy records it. */
  keptAt: string | null;
  open: string | null;
  /** For interview-keyed copies: the interview's id. */
  interviewId: string | null;
}

const META = new Set(["base", "at", "tab", "v", "revision"]);
function words(value: unknown): number {
  if (typeof value === "string") return value.trim() ? value.trim().split(/\s+/).length : 0;
  if (Array.isArray(value)) return value.reduce<number>((n, v) => n + words(v), 0);
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).reduce((n, [k, v]) => n + (META.has(k) ? 0 : words(v)), 0);
  }
  return 0;
}

export function describeCopy(userId: string, key: string): DeviceCopy | null {
  const kind = KINDS.find((k) => key.startsWith(k.prefix(userId)));
  const raw = kind ? readCopy(key) : null;
  if (!kind || raw === null || !raw.trim()) return null;
  const rest = key.slice(kind.prefix(userId).length);
  let parsed: unknown = raw;
  try {
    parsed = JSON.parse(raw);
  } catch {
    /* plain text */
  }
  const keptAt = parsed && typeof parsed === "object" && typeof (parsed as { at?: unknown }).at === "string" ? (parsed as { at: string }).at : null;
  return {
    key, kind, keptAt,
    size: kind.code ? raw.split("\n").length : words(parsed),
    open: kind.open?.(rest) ?? null,
    interviewId: kind.interview ? head(head(rest, ":"), ".") : null,
  };
}

/** This account's copies on this device, newest kinds first in the order above. */
export function deviceCopies(userId: string): DeviceCopy[] {
  return localWorkKeys(userId).map((k) => describeCopy(userId, k)).filter((c): c is DeviceCopy => c !== null)
    .sort((a, b) => KINDS.indexOf(a.kind) - KINDS.indexOf(b.kind) || a.key.localeCompare(b.key));
}

