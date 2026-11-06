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
