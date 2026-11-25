#!/usr/bin/env node
/**
 * The Content-Security-Policy's connect-src must name exactly the API origin the build calls
 * (VITE_API_BASE_URL is baked into the bundle at build time, so the image's policy is too).
 * Changing an environment variable on a running web container changes neither.
 *
 *   node scripts/csp-origin.mjs "$VITE_API_BASE_URL"                       → prints the origin
 *   node scripts/csp-origin.mjs "$VITE_API_BASE_URL" --write TEMPLATE OUT   → fills the template
 *
 * Parsed with the standard URL parser, so the origin is what a browser would compute:
 * - lower-case host;
 * - no default port;
 * - a path is allowed and dropped from the origin (the app calls <base>/api/v1/...).
 * Refused, so the build fails with the reason:
 * - empty, or not a URL;
 * - a scheme other than http(s);
 * - credentials, a query or a fragment;
 * - an IPv6 literal (CSP host sources don't take them);
 * - quotes, spaces, semicolons or control characters, which could break out of the header.
 * --write replaces the single __API_ORIGIN__ placeholder and fails if there isn't exactly one,
 * so nothing else in the template can change.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export function apiOrigin(value) {
  if (!value) throw new Error("VITE_API_BASE_URL is empty: the web image needs the API's full http(s) URL");
  if (/[\s"'`;,\\\u0000-\u001f\u007f]/.test(value)) {
    throw new Error("VITE_API_BASE_URL contains spaces, quotes, commas, semicolons or control characters");
  }
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new Error("VITE_API_BASE_URL isn't a URL");
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") throw new Error("VITE_API_BASE_URL must be http or https");
  if (url.username || url.password) throw new Error("VITE_API_BASE_URL must not contain credentials");
  if (url.search || url.hash) throw new Error("VITE_API_BASE_URL must not have a query or a fragment");
  if (url.hostname.startsWith("[")) throw new Error("VITE_API_BASE_URL: use a host name, not an IPv6 address");
  return url.origin;
}

export function fillTemplate(template, origin) {
  const count = template.split("__API_ORIGIN__").length - 1;
  if (count !== 1) throw new Error(`the security-headers template must contain __API_ORIGIN__ exactly once (found ${count})`);
  return template.replace("__API_ORIGIN__", origin);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    const origin = apiOrigin(process.argv[2]);
    const at = process.argv.indexOf("--write");
    if (at !== -1) {
      writeFileSync(process.argv[at + 2], fillTemplate(readFileSync(process.argv[at + 1], "utf8"), origin));
    }
    process.stdout.write(origin + "\n");
  } catch (e) {
    console.error(`csp-origin: ${e.message}`);
    process.exit(1);
  }
}
