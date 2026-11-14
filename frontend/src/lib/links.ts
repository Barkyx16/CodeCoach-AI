/**
 * Links that come from data (a meeting link or job posting the learner typed, a reference in the
 * content) follow the rule the server applies when it saves them
 * (backend/app/schemas/applications.py:_http_link): an absolute http:// or https:// URL with no
 * spaces. Anything else is shown as text instead of becoming a link, so a `javascript:` or `data:`
 * URL that reached the page some other way (an older row, a path that skipped the check) can't run.
 * React 18 doesn't block `javascript:` in href.
 */
export function externalHref(url: string | null | undefined): string | undefined {
  const v = (url ?? "").trim();
  if (!v || /\s/.test(v)) return undefined;
  return /^https?:\/\/[^/]/i.test(v) ? v : undefined;
}

/** A path inside the app ("/history?type=…"), for links built from navigation state. */
export function appPath(path: string | null | undefined): string | undefined {
  return path && path.startsWith("/") && !path.startsWith("//") ? path : undefined;
}

/** Sign-in and recovery screens: never somewhere to return to afterwards (that would loop). */
const NOT_A_DESTINATION = ["/login", "/register", "/forgot-password", "/reset-password"];

/**
 * Where to go back to after signing in or confirming an email: a path inside this app, else
 * `fallback`. The value comes from router state or this browser's storage, so it's checked like
 * input: "//evil.example" and "/\evil.example" leave the site in a browser, control characters
 * are dropped by browsers (so "/\t/evil.example" becomes "//evil.example"), and an auth screen
 * (or anything in `exclude`) would send the learner round in a loop.
 */
export function safeReturnPath(raw: unknown, fallback: string, exclude: readonly string[] = []): string {
  if (typeof raw !== "string" || raw.length > 2000 || !raw.startsWith("/")) return fallback;
  if ([...raw].some((ch) => ch === "\\" || ch.charCodeAt(0) < 32 || ch.charCodeAt(0) === 127)) return fallback;
  let url: URL;
  try {
    url = new URL(raw, "https://app.invalid");
  } catch {
    return fallback;
  }
  if (url.origin !== "https://app.invalid") return fallback;
  const path = url.pathname.replace(/\/+$/, "") || "/";
  if ([...NOT_A_DESTINATION, ...exclude].includes(path)) return fallback;
  return url.pathname + url.search + url.hash;
}
