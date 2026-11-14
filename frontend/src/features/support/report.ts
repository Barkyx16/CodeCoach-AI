import { routeTitle } from "@/app/routeTitles";
import type { FailedRequest } from "@/lib/supportLog";
import { maskPath } from "@/lib/supportLog";

/**
 * A support report the learner can read before keeping or sharing it (Volume 7, prompt 8).
 *
 * Built from an allowlist: every field is named here and nothing else is copied in. It holds what
 * helps someone diagnose a problem (which build, which page, what failed and its request id, what
 * the server said it can do) and nothing private: no answers, code, notes, transcripts, targets,
 * email address, account id, token, cookie, header, query string or full user agent. Every value
 * is a fixed word, a number, or a string cut to a set length, so the report stays small (a few KB).
 */
export const REPORT_FORMAT = "codecoach-support-report";
export const REPORT_VERSION = 1;
export const MAX_DESCRIPTION = 500;

/** A failure the learner asked for help with (from the message next to the control). */
export interface ReportedError {
  action: string; // "Your submission", "The hint": the app's own wording, never user text
  category: string; // failureKind: offline, busy, unavailable, invalid, …
  code: string | null;
  status: number | null;
  request_id: string | null;
}

/**
 * What each category establishes, and no more: "offline" means no reply came back, which can't
 * tell a dropped connection from a server that's down, so it's never called an outage.
 */
export const CATEGORY_MEANING: Record<string, string> = {
  offline: "No reply came back. The connection or the server; this report can't tell which.",
  busy: "The server asked for a wait before trying again.",
  unavailable: "The server replied that a service it needs is unavailable.",
  invalid: "The server didn't accept what was sent.",
  signed_out: "The session had ended.",
  forbidden: "The server refused: not allowed for this account.",
  not_found: "The server didn't find it.",
  conflict: "It had changed elsewhere meanwhile.",
  server: "The server replied with a fault on its side.",
  other: "Not one of the known kinds.",
};

/** The server's own statement, from GET /capabilities (public, no configuration values). */
export interface ServerStatement {
  code_judge: string | null; // ready | unavailable | not_configured
  code_judge_reason: string | null; // ok | judge_unreachable | …
  ai_provider: string | null; // offline | anthropic
  emails_delivered: boolean | null;
}

export interface ReportInput {
  now: Date;
  timeZone: string | null;
  build: string;
  mode: "production" | "development";
  pathname: string;
  userAgent: string;
  language: string | null;
  online: boolean;
  session: "signed_in" | "guest" | "signed_out" | "checking";
  /** "loading": not answered yet; "unavailable": the request failed (an outage, offline). */
  capabilities: ServerStatement | "loading" | "unavailable";
  error: ReportedError | null;
  failures: FailedRequest[];
  description: string;
}

/** Broad browser and platform only: family, major version, OS family. Not a fingerprint. */
export function coarseBrowser(userAgent: string): { browser: string; major: number | null; platform: string } {
  const ua = userAgent || "";
  const pick: [string, RegExp][] = [
    ["Edge", /Edg\/(\d+)/], ["Opera", /OPR\/(\d+)/], ["Firefox", /Firefox\/(\d+)/],
    ["Chrome", /(?:Chrome|CriOS)\/(\d+)/], ["Safari", /Version\/(\d+).*Safari/],
  ];
  let browser = "other";
  let major: number | null = null;
  for (const [name, re] of pick) {
    const m = re.exec(ua);
    if (m) {
      browser = name;
      major = Number(m[1]);
      break;
    }
  }
  const platform = /Android/.test(ua) ? "Android" : /iPhone|iPad|iPod/.test(ua) ? "iOS" : /Windows/.test(ua) ? "Windows"
    : /Mac OS X|Macintosh/.test(ua) ? "macOS" : /Linux|X11/.test(ua) ? "Linux" : "other";
  return { browser, major, platform };
}

const text = (value: unknown, max: number) => (typeof value === "string" ? value.slice(0, max) : null);
/** "en-GB" → "en": the language, not the region. */
const primaryLanguage = (value: unknown) => (typeof value === "string" && /^[A-Za-z]{2,3}\b/.test(value) ? value.slice(0, value.search(/[^A-Za-z]|$/)).toLowerCase() : null);
/** A request id is ours (hex, maybe with dashes): anything else isn't reported as one. */
const requestId = (value: unknown) => (typeof value === "string" && /^[0-9a-f-]{8,64}$/i.test(value) ? value : null);

/** The report, with a fixed shape and field order. */
export function buildSupportReport(input: ReportInput) {
  const { browser, major, platform } = coarseBrowser(input.userAgent);
  const page = maskPath(input.pathname);
  const category = input.error && Object.hasOwn(CATEGORY_MEANING, input.error.category) ? input.error.category : "other";
  return {
    format: REPORT_FORMAT,
    version: REPORT_VERSION,
    created_at: input.now.toISOString(),
    time_zone: typeof input.timeZone === "string" && /^[A-Za-z0-9_+\-/]{1,64}$/.test(input.timeZone) ? input.timeZone : null,
    app: { build: typeof input.build === "string" && /^[A-Za-z0-9._-]{1,40}$/.test(input.build) ? input.build : "unknown", mode: input.mode },
    page: { name: routeTitle(page), path: page },
    browser: { name: browser, major_version: major, platform, language: primaryLanguage(input.language), online: input.online },
    session: input.session,
    server_said: typeof input.capabilities === "string"
      ? (input.capabilities === "loading" ? "not answered yet" : "unknown: the server's status couldn't be loaded")
      : {
          code_judge: text(input.capabilities.code_judge, 32) ?? "unknown",
          code_judge_reason: text(input.capabilities.code_judge_reason, 32) ?? "unknown",
          ai_provider: text(input.capabilities.ai_provider, 32) ?? "unknown",
          emails_delivered: typeof input.capabilities.emails_delivered === "boolean" ? input.capabilities.emails_delivered : "unknown",
        },
    problem: input.error
      ? {
          action: text(input.error.action, 60),
          category: category,
          meaning: CATEGORY_MEANING[category] ?? CATEGORY_MEANING.other,
          code: text(input.error.code, 60),
          status: typeof input.error.status === "number" ? input.error.status : null,
          request_id: requestId(input.error.request_id),
        }
      : null,
    recent_failed_requests: input.failures.slice(-5).map((f) => ({
      at: f.at, method: text(f.method, 8), path: maskPath(f.path), status: f.status, code: text(f.code, 60), request_id: requestId(f.request_id),
    })),
    description: (typeof input.description === "string" ? input.description : "").slice(0, MAX_DESCRIPTION),
  };
}

export type SupportReport = ReturnType<typeof buildSupportReport>;

/** Exactly what's previewed, copied and downloaded. */
export function reportText(report: SupportReport): string {
  return `${JSON.stringify(report, null, 2)}\n`;
}

/** codecoach-support-report-20261108-2105.json (local time, no seconds' noise). */
export function reportFilename(now: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${REPORT_FORMAT}-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}.json`;
}
